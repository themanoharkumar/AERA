"""SystemHealthMonitor monitoring subsystem for AERA.

This module defines the SystemHealthMonitor class, which tracks subsystem states,
compiles aggregated health reports, and verifies startup and shutdown stages.
"""

import logging
import time
from typing import Any, Dict

from src.camera.camera import CameraStatus

logger = logging.getLogger(__name__)


class SystemHealthMonitor:
    """Monitors the overall backend health and audits individual subsystems."""

    def __init__(
        self,
        camera_manager: Any,
        detection_pipeline: Any,
        event_manager: Any,
        decision_engine: Any,
        evidence_manager: Any,
        report_manager: Any,
        alert_manager: Any,
    ) -> None:
        """Initialize the SystemHealthMonitor with subsystem instances.

        Args:
            camera_manager: The CameraManager instance.
            detection_pipeline: The DetectionPipeline instance.
            event_manager: The EventManager instance.
            decision_engine: The DecisionEngine instance.
            evidence_manager: The EvidenceManager instance.
            report_manager: The ReportManager instance.
            alert_manager: The AlertManager instance.
        """
        self.camera_manager = camera_manager
        self.detection_pipeline = detection_pipeline
        self.event_manager = event_manager
        self.decision_engine = decision_engine
        self.evidence_manager = evidence_manager
        self.report_manager = report_manager
        self.alert_manager = alert_manager

    def check_health(self) -> Dict[str, Any]:
        """Verify the state of each subsystem and return the aggregated status.

        Returns:
            Dict containing overall health status and subsystem details.
        """
        subsystems: Dict[str, Dict[str, Any]] = {}
        overall_healthy = True

        # 1. Camera Subsystem
        try:
            cams = self.camera_manager.list_cameras()
            subsystems["camera"] = {
                "status": "healthy",
                "details": f"Registered cameras count: {len(cams)}",
                "timestamp": time.time(),
            }
        except Exception as e:
            overall_healthy = False
            subsystems["camera"] = {
                "status": "unhealthy",
                "details": f"Error: {e}",
                "timestamp": time.time(),
            }

        # 2. Detection Subsystem
        try:
            detectors = self.detection_pipeline.registry.list_detectors()
            subsystems["detection"] = {
                "status": "healthy",
                "details": f"Active detectors: {detectors}",
                "timestamp": time.time(),
            }
        except Exception as e:
            overall_healthy = False
            subsystems["detection"] = {
                "status": "unhealthy",
                "details": f"Error: {e}",
                "timestamp": time.time(),
            }

        # 3. Event Subsystem
        try:
            evs = self.event_manager.list_events()
            subsystems["event"] = {
                "status": "healthy",
                "details": f"Cached events count: {len(evs)}",
                "timestamp": time.time(),
            }
        except Exception as e:
            overall_healthy = False
            subsystems["event"] = {
                "status": "unhealthy",
                "details": f"Error: {e}",
                "timestamp": time.time(),
            }

        # 4. Decision Subsystem
        try:
            rules_cnt = len(self.decision_engine.rules)
            subsystems["decision"] = {
                "status": "healthy",
                "details": f"Configured evaluation rules: {rules_cnt}",
                "timestamp": time.time(),
            }
        except Exception as e:
            overall_healthy = False
            subsystems["decision"] = {
                "status": "unhealthy",
                "details": f"Error: {e}",
                "timestamp": time.time(),
            }

        # 5. Evidence Subsystem
        try:
            records = self.evidence_manager.list_evidence()
            subsystems["evidence"] = {
                "status": "healthy",
                "details": f"Saved evidence packages count: {len(records)}",
                "timestamp": time.time(),
            }
        except Exception as e:
            overall_healthy = False
            subsystems["evidence"] = {
                "status": "unhealthy",
                "details": f"Error: {e}",
                "timestamp": time.time(),
            }

        # 6. Report Subsystem
        try:
            reps = self.report_manager.list_reports()
            subsystems["report"] = {
                "status": "healthy",
                "details": f"Compiled report count: {len(reps)}",
                "timestamp": time.time(),
            }
        except Exception as e:
            overall_healthy = False
            subsystems["report"] = {
                "status": "unhealthy",
                "details": f"Error: {e}",
                "timestamp": time.time(),
            }

        # 7. Alert Subsystem
        try:
            alerts = self.alert_manager.list_alerts()
            subsystems["alert"] = {
                "status": "healthy",
                "details": f"Dispatched alert count: {len(alerts)}",
                "timestamp": time.time(),
            }
        except Exception as e:
            overall_healthy = False
            subsystems["alert"] = {
                "status": "unhealthy",
                "details": f"Error: {e}",
                "timestamp": time.time(),
            }

        status_str = "healthy" if overall_healthy else "unhealthy"
        logger.info("System health check result: %s", status_str)

        return {
            "status": status_str,
            "overall_healthy": overall_healthy,
            "subsystems": subsystems,
            "timestamp": time.time(),
        }

    def verify_startup(self) -> bool:
        """Verify the startup state of all subsystems.

        Returns:
            bool: True if all subsystems report healthy on startup.
        """
        report = self.check_health()
        return report["overall_healthy"]

    def verify_shutdown(self) -> bool:
        """Verify that subsystems shutdown cleanly (no active streams).

        Returns:
            bool: True if system has stopped cleanly.
        """
        try:
            cams = self.camera_manager.list_cameras()
            for cam in cams:
                if cam.status == CameraStatus.STREAMING:
                    logger.warning("Shutdown verification: Camera '%s' is still streaming.", cam.camera_id)
                    return False
            return True
        except Exception as e:
            logger.exception("Shutdown health verification failed: %s", e)
            return False
