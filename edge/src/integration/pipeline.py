"""EmergencyPipeline implementation for AERA.

This module defines the EmergencyPipeline class, orchestrating raw camera frames
through AI detection, event management, policy decisions, evidence capture,
markdown templating, and alert dispatching.
"""

import uuid
import time
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

            # Load Camera Lock & Resolution Configurations
            import os
            incident_clear_timeout = float(os.environ.get("INCIDENT_CLEAR_TIMEOUT", "30.0"))
            camera_cooldown = float(os.environ.get("CAMERA_COOLDOWN", "300.0"))
            enable_camera_lock = os.environ.get("ENABLE_CAMERA_LOCK", "true").lower() == "true"

            # Filter for actual fire/smoke hazard results
            hazard_results = [
                r for r in detection_results
                if r.label.lower() in ("fire", "smoke")
            ]

            # Find matching active incident on this camera
            matching_incident = self.coordinator.incident_manager.find_matching_active_incident(
                camera_id=camera_id,
                detect_type=EventType.FIRE,
                timestamp=time.time(),
                bbox=(0, 0, 0, 0)
            )

            # If no hazard is detected
            if not hazard_results:
                if matching_incident:
                    timestamp = time.time()
                    if timestamp - matching_incident.last_seen_time > incident_clear_timeout:
                        from src.incident.incident import IncidentState
                        matching_incident.status = IncidentState.RESOLVED
                        matching_incident.resolved_time = timestamp
                        matching_incident.add_timeline_event("Incident resolved: scene clear", timestamp, 0.0, (0, 0, 0, 0))
                        logger.info("Incident Resolved: incident %s resolved, starting cooldown.", matching_incident.incident_id)
                        logger.info("Cooldown Started: cooldown started for camera %s.", camera_id)
                        logger.info("Camera Unlocked: camera %s unlocked.", camera_id)
                return alerts

            # Sort hazards by severity: FIRE (4) > SMOKE (3)
            hazard_results = sorted(hazard_results, key=lambda r: 4 if "fire" in r.label.lower() else 3, reverse=True)
            result = hazard_results[0]

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

            # Map EventPriority to trigger policy escalation
            priority = EventPriority.LOW
            if event_type == EventType.FIRE:
                priority = EventPriority.CRITICAL
            elif event_type == EventType.SMOKE:
                priority = EventPriority.HIGH

            bbox = result.bounding_boxes[0] if result.bounding_boxes else (0, 0, 0, 0)
            timestamp = result.timestamp if result.timestamp > 0 else time.time()

            # If no active incident exists, check if camera is in cooldown
            if not matching_incident:
                if self.coordinator.incident_manager.is_camera_in_cooldown(camera_id, timestamp):
                    logger.info("Cooldown Ignore: detection of %s ignored because camera %s is in cooldown.", result.label, camera_id)
                    return alerts

            # Generate annotated frame and original frame bytes
            annotated_frame = frame.copy()
            for r in detection_results:
                if hasattr(r, "bounding_boxes") and r.bounding_boxes:
                    for box in r.bounding_boxes:
                        xmin, ymin, xmax, ymax = box
                        color = (0, 0, 255) if r.label.lower() == "fire" else (0, 165, 255)
                        cv2.rectangle(annotated_frame, (xmin, ymin), (xmax, ymax), color, 2)
                        label_text = f"{r.label.upper()} {r.confidence:.0%}"
                        cv2.putText(annotated_frame, label_text, (xmin, max(15, ymin - 5)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

            success_ann, encoded_ann = cv2.imencode(".jpg", annotated_frame)
            image_bytes = encoded_ann.tobytes() if success_ann else b""
            
            success_orig, encoded_orig = cv2.imencode(".jpg", frame)
            original_bytes = encoded_orig.tobytes() if success_orig else b""

            if matching_incident:
                    # ── UPDATE EXISTING STATEFUL INCIDENT ──
                    logger.info("Incident Matched: incident %s matching camera %s, area %s",
                                matching_incident.incident_id, camera_id, bbox)
                    
                    # Update fields
                    matching_incident.last_seen_time = timestamp
                    matching_incident.confidence = max(matching_incident.confidence, result.confidence)
                    matching_incident.bounding_box = bbox
                    matching_incident.detection_count += 1

                    # Check for new observed hazard
                    is_new_hazard = False
                    if event_type not in matching_incident.observed_hazards:
                        is_new_hazard = True
                        matching_incident.observed_hazards.append(event_type)
                        matching_incident.last_hazard = event_type
                        matching_incident.add_timeline_event(f"New hazard detected: {event_type.value}", timestamp, result.confidence, bbox)
                        logger.info("Hazard Added: %s added to incident %s", event_type.value, matching_incident.incident_id)
                    else:
                        logger.info("Hazard Already Present: %s in incident %s", event_type.value, matching_incident.incident_id)

                    # Check for severity escalation
                    escalation_alert_sent = False
                    if is_new_hazard:
                        from src.incident.incident import IncidentState
                        
                        PRIORITY_RANK = {
                            EventPriority.LOW: 1,
                            EventPriority.MEDIUM: 2,
                            EventPriority.HIGH: 3,
                            EventPriority.CRITICAL: 4
                        }
                        
                        if PRIORITY_RANK.get(priority, 1) > PRIORITY_RANK.get(matching_incident.priority, 1):
                            # Severity Escalation!
                            matching_incident.priority = priority
                            matching_incident.status = IncidentState.UPDATED
                            matching_incident.escalation_count += 1
                            matching_incident.add_timeline_event(f"Severity Escalated to {priority.value}", timestamp, result.confidence, bbox)
                            logger.info("Severity Escalated: incident %s escalated to %s", matching_incident.incident_id, priority.value)
                            
                            # Run decision engine with custom decision ID
                            esc_event_id = str(uuid.uuid4())
                            dec_id = str(uuid.uuid4())
                            esc_event = self.coordinator.event_manager.create_event(
                                event_id=esc_event_id,
                                event_type=event_type,
                                camera_id=camera_id,
                                timestamp=timestamp,
                                description=f"Severity escalated: {event_type.value} detected with confidence {result.confidence:.2f}",
                                confidence=result.confidence,
                                priority=priority,
                                metadata=result.metadata,
                            )
                            decision_result = self.coordinator.decision_engine.evaluate_event(esc_event, decision_id=dec_id)
                            
                            # Compile escalation report and send alert
                            if self.coordinator.incident_manager.hazard_escalation_alert:
                                first_ev = matching_incident.evidence_list[0]
                                report = self.coordinator.report_manager.generate_report(
                                    decision=decision_result,
                                    evidence=first_ev,
                                )
                                alert = self.coordinator.alert_manager.trigger_alert(report)
                                alerts.append(alert)
                                matching_incident.reports.append(report)
                                matching_incident.alerts.append(alert)
                                matching_incident.notification_history.append({
                                    "event": "escalation_alert",
                                    "timestamp": timestamp,
                                    "alert_id": getattr(alert, "alert_id", None)
                                })
                                escalation_alert_sent = True
                                logger.info("Notification Sent: Escalation alert dispatched for incident %s", matching_incident.incident_id)

                    # Suppressed notification log if no escalation alert was sent
                    if not escalation_alert_sent:
                        matching_incident.add_timeline_event(f"Detection updated: {event_type.value}", timestamp, result.confidence, bbox)
                        logger.info("Notification Suppressed: duplicate hazard/no escalation for incident %s", matching_incident.incident_id)

                    # Persist duplicate frames physically under the incident evidence directory
                    import os
                    try:
                        first_ev = matching_incident.evidence_list[0]
                        ev_dir = os.path.dirname(first_ev.image_path)
                        
                        latest_path = os.path.join(ev_dir, "latest.jpg")
                        latest_orig_path = os.path.join(ev_dir, "latest_original.jpg")
                        
                        if image_bytes:
                            with open(latest_path, "wb") as f_latest:
                                f_latest.write(image_bytes)
                        if original_bytes:
                            with open(latest_orig_path, "wb") as f_latest_orig:
                                f_latest_orig.write(original_bytes)

                        # Write historical snapshot
                        snap_name = f"snapshot_{int(timestamp)}.jpg"
                        snap_path = os.path.join(ev_dir, snap_name)
                        
                        # Limit snapshots to 5
                        snap_files = sorted([f for f in os.listdir(ev_dir) if f.startswith("snapshot_")])
                        if len(snap_files) >= 5:
                            try:
                                os.remove(os.path.join(ev_dir, snap_files[0]))
                            except Exception:
                                pass
                        
                        if image_bytes:
                            with open(snap_path, "wb") as f_snap:
                                f_snap.write(image_bytes)

                        # Update metadata.json on disk to sync updated statistics
                        metadata_file = os.path.join(ev_dir, "metadata.json")
                        if os.path.exists(metadata_file):
                            import json
                            with open(metadata_file, "r", encoding="utf-8") as f_r:
                                meta_data_dict = json.load(f_r)
                            
                            custom_m = meta_data_dict.setdefault("custom_metadata", {})
                            custom_m["last_seen_time"] = timestamp
                            custom_m["detection_count"] = matching_incident.detection_count
                            custom_m["latest_confidence"] = result.confidence
                            custom_m["latest_bounding_box"] = bbox
                            custom_m["duration"] = matching_incident.duration
                            custom_m["latest_image_path"] = latest_path.replace("\\", "/")
                            custom_m["observed_hazards"] = [h.value for h in matching_incident.observed_hazards]
                            
                            with open(metadata_file, "w", encoding="utf-8") as f_w:
                                json.dump(meta_data_dict, f_w, indent=4)
                        logger.info("Incident Updated: Saved duplicate evidence files and timeline details to incident %s", matching_incident.incident_id)
                    except Exception as e_dup:
                        logger.error("Failed to save duplicate evidence to disk: %s", e_dup)

            else:
                    # ── CREATE NEW STATEFUL INCIDENT ──
                    event_id = str(uuid.uuid4())
                    decision_id = str(uuid.uuid4())

                    camera_obj = self.coordinator.camera_manager.get_camera(camera_id)
                    camera_name = camera_obj.name if camera_obj else camera_id

                    # 1. Pre-capture and persist Evidence package
                    custom_meta = {
                        "detector_confidence": result.confidence,
                        "label": result.label,
                        "camera_name": camera_name,
                        "bounding_boxes": [bbox],
                        "model_metadata": getattr(result, "metadata", {}),
                        "observed_hazards": [event_type.value],
                    }

                    evidence_metadata = EvidenceMetadata(
                        camera_id=camera_id,
                        event_id=event_id,
                        decision_id=decision_id,
                        timestamp=timestamp,
                        detector_name=result.detector_name,
                        file_size=len(image_bytes),
                        resolution=(frame.shape[1], frame.shape[0]) if len(frame.shape) >= 2 else (0, 0),
                        custom_metadata=custom_meta,
                    )

                    try:
                        evidence_package = self.coordinator.evidence_manager.create_evidence(
                            event_id=event_id,
                            decision_id=decision_id,
                            metadata=evidence_metadata,
                            image_data=image_bytes,
                        )

                        # Save original.jpg
                        import os
                        ev_dir = os.path.dirname(evidence_package.image_path)
                        orig_path = os.path.join(ev_dir, "original.jpg")
                        if original_bytes:
                            with open(orig_path, "wb") as f_orig:
                                f_orig.write(original_bytes)
                        
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
                                
                    except Exception as e_ev:
                        logger.error("Evidence capture/save failed: %s. Aborting incident creation.", e_ev)
                        return alerts

                    # 2. Verify evidence saved successfully
                    if not self.coordinator.incident_manager.verify_evidence(evidence_package):
                        logger.error("Evidence verification failed for event %s. Aborting incident creation.", event_id)
                        return alerts

                    # 3. Create Event in EventManager
                    event = self.coordinator.event_manager.create_event(
                        event_id=event_id,
                        event_type=event_type,
                        camera_id=camera_id,
                        timestamp=timestamp,
                        description=f"AI detection of {result.label} with confidence {result.confidence:.2f}",
                        confidence=result.confidence,
                        priority=priority,
                        metadata=result.metadata,
                    )

                    # 4. Evaluate via DecisionEngine
                    decision_result = self.coordinator.decision_engine.evaluate_event(event, decision_id=decision_id)

                    # 5. Compile Report and trigger Alert
                    report = self.coordinator.report_manager.generate_report(
                        decision=decision_result,
                        evidence=evidence_package,
                    )

                    alert = self.coordinator.alert_manager.trigger_alert(report)
                    alerts.append(alert)

                    # 6. Instantiate and register Incident
                    from src.incident.incident import Incident, IncidentState
                    new_incident = Incident(
                        incident_id=event_id,
                        incident_type=event_type,
                        camera_id=camera_id,
                        start_time=timestamp,
                        priority=priority,
                        status=IncidentState.ACTIVE,
                        confidence=result.confidence,
                        bounding_box=bbox,
                        evidence_list=[evidence_package],
                        description=event.description,
                    )
                    new_incident.reports.append(report)
                    new_incident.alerts.append(alert)
                    
                    self.coordinator.incident_manager.register_incident(new_incident)
                    logger.info("Incident Created: incident %s created.", new_incident.incident_id)
                    logger.info("Camera Locked: camera %s locked.", camera_id)

        except Exception as e:
            logger.exception("Error executing pipeline flow for camera %s", camera_id)
            if isinstance(e, PipelineError):
                raise
            raise PipelineError(f"Pipeline flow failed: {e}") from e

        return alerts
