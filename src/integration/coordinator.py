"""SystemCoordinator coordination layer for AERA.

This module defines the SystemCoordinator class, which connects all subsystems,
performs interface checks, and orchestrates startup and shutdown lifecycles.
"""

import logging
from typing import Any, Optional

from src.camera.manager import CameraManager
from src.detection.fire.detector import FireDetector
from src.detection.pipeline import DetectionPipeline
from src.detection.registry import DetectorRegistry
from src.detection.smoke.detector import SmokeDetector
from src.decision.engine import DecisionEngine
from src.event.manager import EventManager
from src.evidence.manager import EvidenceManager
from src.report.manager import ReportManager
from src.alert.manager import AlertManager

from src.integration.exceptions import ValidationError
from src.integration.validator import SystemValidator
from src.integration.health import SystemHealthMonitor

logger = logging.getLogger(__name__)


class SystemCoordinator:
    """Coordinates lifecycle, connection, and health monitoring of all backend components.

    Ensures dependencies are correctly set up and validated before starting streams or pipelines.
    """

    def __init__(
        self,
        camera_manager: Optional[CameraManager] = None,
        detection_pipeline: Optional[DetectionPipeline] = None,
        event_manager: Optional[EventManager] = None,
        decision_engine: Optional[DecisionEngine] = None,
        evidence_manager: Optional[EvidenceManager] = None,
        report_manager: Optional[ReportManager] = None,
        alert_manager: Optional[AlertManager] = None,
    ) -> None:
        """Initialize the coordinator with optional subsystem overrides."""
        self.camera_manager = camera_manager if camera_manager is not None else CameraManager()

        if detection_pipeline is not None:
            self.detection_pipeline = detection_pipeline
        else:
            import os
            from src.detection.detectors.yolo_fire_smoke_detector import YOLOFireSmokeDetector
            
            yolo_model_path = os.environ.get("YOLO_MODEL_PATH", "ai/models/fire_smoke_v1.pt")
            fire_threshold = float(os.environ.get("YOLO_FIRE_THRESHOLD", "0.35"))
            smoke_threshold = float(os.environ.get("YOLO_SMOKE_THRESHOLD", "0.30"))
            
            registry = DetectorRegistry()
            registry.register_detector(
                "fire_detector",
                YOLOFireSmokeDetector(
                    model_path=yolo_model_path,
                    class_label="fire",
                    confidence_threshold=fire_threshold,
                )
            )
            registry.register_detector(
                "smoke_detector",
                YOLOFireSmokeDetector(
                    model_path=yolo_model_path,
                    class_label="smoke",
                    confidence_threshold=smoke_threshold,
                )
            )
            self.detection_pipeline = DetectionPipeline(registry)

        self.event_manager = event_manager if event_manager is not None else EventManager()
        
        if decision_engine is not None:
            self.decision_engine = decision_engine
        else:
            from src.decision.engine import DecisionEngine
            from src.decision.rules import ConfidenceThresholdRule, SeverityCalculationRule, ActionDeterminationRule
            # Custom rules to prevent duplicate suppression/cooldown logic inside DecisionEngine
            custom_rules = [
                ConfidenceThresholdRule(),
                SeverityCalculationRule(),
                ActionDeterminationRule(),
            ]
            self.decision_engine = DecisionEngine(rules=custom_rules)
            
        self.evidence_manager = evidence_manager if evidence_manager is not None else EvidenceManager()
        self.report_manager = report_manager if report_manager is not None else ReportManager()
        self.alert_manager = alert_manager if alert_manager is not None else AlertManager()

        # Instantiate IncidentManager
        import os
        from src.incident.manager import IncidentManager
        cooldown_duration = float(os.environ.get("INCIDENT_COOLDOWN", "300.0"))
        iou_threshold = float(os.environ.get("AREA_IOU_THRESHOLD", "0.40"))
        centroid_distance_threshold = float(os.environ.get("CENTROID_DISTANCE_THRESHOLD", "120.0"))
        self.incident_manager = IncidentManager(
            cooldown_duration=cooldown_duration,
            iou_threshold=iou_threshold,
            centroid_distance_threshold=centroid_distance_threshold,
        )

        # Instantiate helper tools
        self.validator = SystemValidator()
        self.health_monitor = SystemHealthMonitor(
            camera_manager=self.camera_manager,
            detection_pipeline=self.detection_pipeline,
            event_manager=self.event_manager,
            decision_engine=self.decision_engine,
            evidence_manager=self.evidence_manager,
            report_manager=self.report_manager,
            alert_manager=self.alert_manager,
        )

        self._started = False

    def start(self) -> None:
        """Perform startup validations, connect dependencies, and flag the system as active."""
        if self._started:
            logger.warning("SystemCoordinator is already started.")
            return

        logger.info("Starting SystemCoordinator...")

        # 1. Audit method signatures and presence
        self.validator.validate_system(
            camera_manager=self.camera_manager,
            detection_pipeline=self.detection_pipeline,
            event_manager=self.event_manager,
            decision_engine=self.decision_engine,
            evidence_manager=self.evidence_manager,
            report_manager=self.report_manager,
            alert_manager=self.alert_manager,
        )

        # 2. Load model weights for detectors in the registry
        for name in self.detection_pipeline.registry.list_detectors():
            try:
                detector = self.detection_pipeline.registry.get_detector(name)
                if hasattr(detector, "load_model") and callable(detector.load_model):
                    detector.load_model()
                    logger.info("Loaded weights for detector: %s", name)
            except Exception as e:
                logger.error("Failed to load weights for detector '%s': %s", name, e)
                raise ValidationError(f"Failed to load weights for detector '{name}': {e}") from e

        # 3. Verify startup health status
        if not self.health_monitor.verify_startup():
            raise ValidationError("Subsystems startup verification failed.")

        self._started = True
        logger.info("SystemCoordinator successfully started.")

    def stop(self) -> None:
        """Disconnect camera streams and release subsystem caches cleanly."""
        if not self._started:
            logger.warning("SystemCoordinator is not active.")
            return

        logger.info("Stopping SystemCoordinator...")

        # 1. Stop all camera streams in CameraManager
        try:
            self.camera_manager.shutdown()
        except Exception as e:
            logger.error("Error shutting down camera streams: %s", e)

        # 2. Clear caches in all managers
        try:
            self.event_manager.clear_events()
        except Exception as e:
            logger.error("Error clearing EventManager: %s", e)

        try:
            self.decision_engine.clear()
        except Exception as e:
            logger.error("Error clearing DecisionEngine: %s", e)

        try:
            self.evidence_manager.clear()
        except Exception as e:
            logger.error("Error clearing EvidenceManager: %s", e)

        try:
            self.report_manager.clear()
        except Exception as e:
            logger.error("Error clearing ReportManager: %s", e)

        try:
            self.alert_manager.clear()
        except Exception as e:
            logger.error("Error clearing AlertManager: %s", e)

        try:
            self.incident_manager.clear()
        except Exception as e:
            logger.error("Error clearing IncidentManager: %s", e)

        self._started = False

        # 3. Verify shutdown status
        if not self.health_monitor.verify_shutdown():
            logger.warning("Subsystems shutdown health verification flagged warnings.")

        logger.info("SystemCoordinator stopped cleanly.")

    @property
    def is_started(self) -> bool:
        """Check if the coordinator has been started and is currently active.

        Returns:
            bool: True if started.
        """
        return self._started
