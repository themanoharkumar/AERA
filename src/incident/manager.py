import logging
import math
import threading
from typing import Any, Dict, List, Optional, Tuple

from src.incident.incident import Incident, IncidentState
from src.event.types import EventType

logger = logging.getLogger(__name__)

class IncidentManager:
    """Thread-safe manager for orchestrating AERA emergency incident lifecycles."""

    def __init__(
        self,
        cooldown_duration: float = 300.0,
        iou_threshold: float = 0.40,
        centroid_distance_threshold: float = 120.0,
    ) -> None:
        import os
        self._incidents: Dict[str, Incident] = {}
        self.cooldown_duration = cooldown_duration
        self.iou_threshold = iou_threshold
        self.centroid_distance_threshold = centroid_distance_threshold
        self.enable_unified_hazards = os.environ.get("ENABLE_UNIFIED_HAZARDS", "true").lower() == "true"
        self.allow_hazard_escalation = os.environ.get("ALLOW_HAZARD_ESCALATION", "true").lower() == "true"
        self.hazard_escalation_alert = os.environ.get("HAZARD_ESCALATION_ALERT", "true").lower() == "true"
        self.enable_camera_lock = os.environ.get("ENABLE_CAMERA_LOCK", "true").lower() == "true"
        self.camera_cooldown = float(os.environ.get("CAMERA_COOLDOWN", "300.0"))
        self._lock = threading.Lock()

    def _is_area_match(self, boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> bool:
        """Evaluate if two bounding boxes are in the same area using IoU or Centroid distance."""
        if not boxA or not boxB:
            return False
            
        # Calculate centroids
        cxA = (boxA[0] + boxA[2]) / 2.0
        cyA = (boxA[1] + boxA[3]) / 2.0
        cxB = (boxB[0] + boxB[2]) / 2.0
        cyB = (boxB[1] + boxB[3]) / 2.0
        
        dist = math.sqrt((cxA - cxB) ** 2 + (cyA - cyB) ** 2)
        if dist <= self.centroid_distance_threshold:
            logger.info("Area match found via centroid distance: %.1f px (threshold: %.1f px)", dist, self.centroid_distance_threshold)
            return True
            
        # Calculate IoU
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        
        interArea = max(0, xB - xA) * max(0, yB - yA)
        if interArea > 0:
            boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
            boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
            iou = interArea / float(boxAArea + boxBArea - interArea)
            if iou >= self.iou_threshold:
                logger.info("Area match found via IoU: %.2f (threshold: %.2f)", iou, self.iou_threshold)
                return True
                
        return False

    def find_matching_active_incident(
        self,
        camera_id: str,
        detect_type: EventType,
        timestamp: float,
        bbox: Tuple[int, int, int, int]
    ) -> Optional[Incident]:
        """Find matching active incident considering spatial matching, camera locking, and cooldown."""
        with self._lock:
            # Active states participating in cooldown / duplicate suppression
            active_states = {IncidentState.NEW, IncidentState.ACTIVE, IncidentState.UPDATED}
            
            if self.enable_camera_lock:
                # Core Rule: Each camera may have only ONE ACTIVE incident at a time.
                # If an active incident exists on this camera, always return it.
                for inc in self._incidents.values():
                    if inc.status in active_states and inc.camera_id == camera_id:
                        return inc
                return None
            
            for inc in self._incidents.values():
                if inc.status not in active_states or inc.camera_id != camera_id:
                    continue
                
                # Check cooldown duration (default 5 minutes)
                time_elapsed = abs(timestamp - inc.last_seen_time)
                if time_elapsed > self.cooldown_duration:
                    logger.info("Incident %s ignored for matching: Cooldown window expired (%.1fs > %.1fs)",
                                inc.incident_id, time_elapsed, self.cooldown_duration)
                    continue
                
                if self.enable_unified_hazards:
                    # Unified Hazard Incident Model: Match strictly on camera and area
                    if self._is_area_match(inc.bounding_box, bbox):
                        return inc
                else:
                    # Legacy/Fallback Detection-Type matching logic
                    is_type_match = False
                    if inc.primary_hazard == detect_type:
                        is_type_match = True
                    elif inc.primary_hazard == EventType.FIRE and detect_type == EventType.SMOKE:
                        is_type_match = True
                    
                    if is_type_match and self._is_area_match(inc.bounding_box, bbox):
                        return inc
            return None

    def is_camera_in_cooldown(self, camera_id: str, timestamp: float) -> bool:
        """Check if the camera is currently in its post-resolution cooldown period."""
        with self._lock:
            resolved_incidents = [
                inc for inc in self._incidents.values()
                if inc.camera_id == camera_id and inc._status == IncidentState.RESOLVED
            ]
            if not resolved_incidents:
                return False
                
            # Find the most recently resolved incident on this camera
            most_recent = max(
                resolved_incidents,
                key=lambda inc: inc.resolved_time if inc.resolved_time is not None else inc.last_seen_time
            )
            resolved_t = most_recent.resolved_time if most_recent.resolved_time is not None else most_recent.last_seen_time
            
            time_elapsed = timestamp - resolved_t
            if 0 <= time_elapsed <= self.camera_cooldown:
                logger.info("Camera %s is in Cooldown (elapsed: %.1fs, limit: %.1fs)", camera_id, time_elapsed, self.camera_cooldown)
                return True
            else:
                if not getattr(most_recent, "_cooldown_finished_logged", False):
                    most_recent._cooldown_finished_logged = True
                    logger.info("Cooldown Finished: cooldown finished for camera %s.", camera_id)
                    logger.info("Camera Ready: camera %s ready.", camera_id)
                return False

    def verify_evidence(self, evidence: Any) -> bool:
        """Verify that the evidence package physically exists on disk and is valid."""
        import os
        if not evidence:
            logger.error("Evidence Validation Failed: Evidence object is None.")
            return False
            
        # Check annotated image
        if not evidence.image_path or not os.path.exists(evidence.image_path):
            logger.error("Evidence Validation Failed: Annotated image does not exist: %s", getattr(evidence, 'image_path', None))
            return False
            
        # Check metadata json file
        ev_dir = os.path.dirname(evidence.image_path)
        metadata_file = os.path.join(ev_dir, "metadata.json")
        if not os.path.exists(metadata_file):
            logger.error("Evidence Validation Failed: Metadata JSON file does not exist: %s", metadata_file)
            return False
            
        # Check original image
        custom_meta = evidence.metadata.get("custom_metadata", {})
        original_image_path = custom_meta.get("original_image_path")
        if not original_image_path or not os.path.exists(original_image_path):
            logger.error("Evidence Validation Failed: Original image does not exist: %s", original_image_path)
            return False
            
        # Check bounding boxes are stored
        bboxes = custom_meta.get("bounding_boxes", [])
        if not bboxes:
            logger.error("Evidence Validation Failed: Bounding boxes list is empty.")
            return False
            
        logger.info("Evidence Validation Passed: Evidence package successfully verified on disk.")
        return True

    def register_incident(self, incident: Incident) -> None:
        with self._lock:
            self._incidents[incident.incident_id] = incident
            logger.info("Incident Registered: %s (Type: %s, State: %s)",
                        incident.incident_id, incident.incident_type.value, incident.status.value)

    def list_incidents(self) -> List[Incident]:
        with self._lock:
            return list(self._incidents.values())

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        with self._lock:
            return self._incidents.get(incident_id)

    def clear(self) -> None:
        with self._lock:
            self._incidents.clear()
            logger.info("IncidentManager cleared.")
