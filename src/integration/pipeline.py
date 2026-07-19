"""EmergencyPipeline implementation for AERA.

This module defines the EmergencyPipeline class, orchestrating raw camera frames
through AI detection, event management, policy decisions, evidence capture,
markdown templating, and alert dispatching.
"""

import logging
from typing import List, Optional
import cv2
import numpy as np

from src.alert.alert import Alert
from src.camera.camera import CameraStatus
from src.event.types import EventType
from src.event.priority import EventPriority
from src.evidence.metadata import EvidenceMetadata
from src.integration.coordinator import SystemCoordinator
from src.integration.exceptions import PipelineError

logger = logging.getLogger(__name__)


class EmergencyPipeline:
    """Orchestrates the complete AERA backend data flow from camera frame to alert dispatch.

    Conforms to the exact architectural order:
    Camera Frame -> Detection -> Event -> Decision -> Evidence -> Report -> Alert
    """

    def __init__(self, coordinator: SystemCoordinator) -> None:
        """Initialize the pipeline with a SystemCoordinator orchestrator.

        Args:
            coordinator: An active SystemCoordinator instance.
        """
        self.coordinator = coordinator

    def process_camera_frame(self, camera_id: str, frame: np.ndarray) -> List[Alert]:
        """Process a single video frame through the complete end-to-end pipeline.

        Args:
            camera_id: Unique camera source identifier.
            frame: A NumPy array containing frame image data.

        Returns:
            A list of successfully dispatched Alert records.

        Raises:
            PipelineError: If camera fails or pipeline execution encounters errors.
        """
        # Verify camera exists and is active/streaming
        try:
            status = self.coordinator.camera_manager.camera_status(camera_id)
            if status != CameraStatus.STREAMING:
                raise PipelineError(f"Camera failure: Camera '{camera_id}' is not in STREAMING status (current: {status.value}).")
        except Exception as e:
            if isinstance(e, PipelineError):
                raise
            raise PipelineError(f"Camera failure: Camera '{camera_id}' not found or invalid: {e}") from e

        if frame is None or not isinstance(frame, np.ndarray):
            logger.error("Invalid frame received for camera %s", camera_id)
            raise PipelineError(f"Camera failure: Invalid frame received for camera '{camera_id}'.")

        alerts: List[Alert] = []

        try:
            # 1. Trigger AI Model detection
            detection_results = self.coordinator.detection_pipeline.process_frame(frame)

            for result in detection_results:
                # Map detector label to EventType
                label_upper = result.label.upper()
                try:
                    event_type = EventType(label_upper)
                except ValueError:
                    if "FIRE" in label_upper:
                        event_type = EventType.FIRE
                    elif "SMOKE" in label_upper:
                        event_type = EventType.SMOKE
                    else:
                        event_type = EventType.FIRE

                # 2. Map EventPriority to trigger policy escalation
                priority = EventPriority.LOW
                if event_type == EventType.FIRE:
                    priority = EventPriority.CRITICAL
                elif event_type == EventType.SMOKE:
                    priority = EventPriority.HIGH

                # Translate/register event in EventManager
                event = self.coordinator.event_manager.create_event(
                    event_type=event_type,
                    camera_id=camera_id,
                    description=f"AI detection of {result.label} with confidence {result.confidence:.2f}",
                    confidence=result.confidence,
                    priority=priority,
                    metadata=result.metadata,
                )

                # 3. Evaluate event through DecisionEngine policies
                decision_result = self.coordinator.decision_engine.evaluate_event(event)

                # 4. Trigger escalated alert procedures if policy requires action
                if decision_result.action == "escalate":
                    # Generate annotated frame by drawing bounding boxes
                    annotated_frame = frame.copy()
                    for r in detection_results:
                        if hasattr(r, "bounding_boxes") and r.bounding_boxes:
                            for box in r.bounding_boxes:
                                xmin, ymin, xmax, ymax = box
                                # Draw box: red for fire, orange for smoke
                                color = (0, 0, 255) if r.label.lower() == "fire" else (0, 165, 255)
                                cv2.rectangle(annotated_frame, (xmin, ymin), (xmax, ymax), color, 2)
                                label_text = f"{r.label.upper()} {r.confidence:.0%}"
                                cv2.putText(annotated_frame, label_text, (xmin, max(15, ymin - 5)),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

                    # Encode annotated image
                    success_ann, encoded_ann = cv2.imencode(".jpg", annotated_frame)
                    image_bytes = encoded_ann.tobytes() if success_ann else b""
                    
                    # Encode original image
                    success_orig, encoded_orig = cv2.imencode(".jpg", frame)
                    original_bytes = encoded_orig.tobytes() if success_orig else b""

                    camera_obj = self.coordinator.camera_manager.get_camera(camera_id)
                    camera_name = camera_obj.name if camera_obj else camera_id
                    
                    custom_meta = {
                        "detector_confidence": result.confidence,
                        "label": result.label,
                        "camera_name": camera_name,
                        "bounding_boxes": getattr(result, "bounding_boxes", []),
                        "model_metadata": getattr(result, "metadata", {}),
                    }
                    
                    evidence_metadata = EvidenceMetadata(
                        camera_id=camera_id,
                        event_id=event.event_id,
                        decision_id=decision_result.decision_id,
                        timestamp=event.timestamp,
                        detector_name=result.detector_name,
                        file_size=len(image_bytes),
                        resolution=(frame.shape[1], frame.shape[0])
                        if len(frame.shape) >= 2
                        else (0, 0),
                        custom_metadata=custom_meta,
                    )

                    # 5. Persist physical files with EvidenceManager
                    evidence_package = self.coordinator.evidence_manager.create_evidence(
                        event_id=event.event_id,
                        decision_id=decision_result.decision_id,
                        metadata=evidence_metadata,
                        image_data=image_bytes,
                    )

                    # Save original image as original.jpg in the same directory
                    if original_bytes and evidence_package.image_path:
                        import os
                        try:
                            ev_dir = os.path.dirname(evidence_package.image_path)
                            orig_path = os.path.join(ev_dir, "original.jpg")
                            with open(orig_path, "wb") as f_orig:
                                f_orig.write(original_bytes)
                            
                            # Link saved original frame to the metadata
                            orig_url_path = orig_path.replace("\\", "/")
                            evidence_package.metadata.setdefault("custom_metadata", {})["original_image_path"] = orig_url_path
                            
                            # Update metadata.json with the new path
                            metadata_file = os.path.join(ev_dir, "metadata.json")
                            if os.path.exists(metadata_file):
                                import json
                                with open(metadata_file, "r", encoding="utf-8") as f_r:
                                    meta_data_dict = json.load(f_r)
                                meta_data_dict.setdefault("custom_metadata", {})["original_image_path"] = orig_url_path
                                with open(metadata_file, "w", encoding="utf-8") as f_w:
                                    json.dump(meta_data_dict, f_w, indent=4)
                            logger.info("Saved original frame evidence and updated metadata at: %s", orig_path)
                        except Exception as e_orig:
                            logger.error("Failed to save original frame to disk: %s", e_orig)

                    # 6. Render report layout with ReportEngine
                    report = self.coordinator.report_manager.generate_report(
                        decision=decision_result,
                        evidence=evidence_package,
                    )

                    # 7. Dispatches alert console notification via AlertManager
                    alert = self.coordinator.alert_manager.trigger_alert(report)
                    alerts.append(alert)

        except Exception as e:
            logger.exception("Error executing pipeline flow for camera %s", camera_id)
            if isinstance(e, PipelineError):
                raise
            raise PipelineError(f"Pipeline flow failed: {e}") from e

        return alerts
