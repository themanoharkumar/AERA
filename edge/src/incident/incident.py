from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from src.event.status import EventStatus
from src.event.types import EventType
from src.event.priority import EventPriority

class IncidentState(str, Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    UPDATED = "UPDATED"
    RESOLVED = "RESOLVED"
    ARCHIVED = "ARCHIVED"

class CompatibleStatus(str):
    def __new__(cls, val: str, state_enum: IncidentState):
        obj = str.__new__(cls, val)
        obj.state_enum = state_enum
        return obj

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, EventStatus):
            if self.state_enum == IncidentState.NEW:
                return other == EventStatus.NEW
            elif self.state_enum in (IncidentState.ACTIVE, IncidentState.UPDATED):
                return other in (EventStatus.PROCESSING, EventStatus.VERIFIED)
            elif self.state_enum == IncidentState.RESOLVED:
                return other == EventStatus.RESOLVED
            else:
                return other == EventStatus.RESOLVED
        if isinstance(other, IncidentState):
            return self.state_enum == other
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.state_enum)

    @property
    def value(self) -> str:
        return self.state_enum.value

class Incident:
    """Represents a managed emergency response incident in AERA."""

    def __init__(
        self,
        incident_id: str,
        incident_type: Any,  # First observed hazard (EventType)
        camera_id: str,
        start_time: float,
        priority: Any,      # EventPriority
        status: IncidentState,
        confidence: float,
        bounding_box: Tuple[int, int, int, int],
        evidence_list: Optional[List[Any]] = None,
        detection_count: int = 1,
        description: str = "",
    ) -> None:
        self.incident_id = incident_id
        self.camera_id = camera_id
        self.start_time = start_time
        self.last_seen_time = start_time
        self.priority = priority
        self._status = status
        self.confidence = confidence
        self.bounding_box = bounding_box
        self.evidence_list = evidence_list if evidence_list is not None else []
        self.detection_count = detection_count
        self.description = description
        
        # Unified Hazard fields
        self.observed_hazards: List[Any] = [incident_type] if incident_type else []
        self.last_hazard: Any = incident_type
        self.escalation_count: int = 0
        self.notification_history: List[Dict[str, Any]] = []
        self.resolved_time: Optional[float] = None

        self.timeline: List[Dict[str, Any]] = []
        self.reports: List[Any] = []
        self.alerts: List[Any] = []
        
        self.add_timeline_event("Incident created", start_time, confidence, bounding_box)

    @property
    def duration(self) -> float:
        return self.last_seen_time - self.start_time

    @property
    def primary_hazard(self) -> Any:
        """Dynamically compute the hazard with the highest priority rank."""
        HAZARD_PRIORITY = {
            EventType.FIRE: EventPriority.CRITICAL,
            EventType.SMOKE: EventPriority.HIGH,
            EventType.VIOLENCE: EventPriority.CRITICAL,
            EventType.INTRUSION: EventPriority.HIGH,
            EventType.CROWD: EventPriority.MEDIUM,
            EventType.FALL: EventPriority.LOW
        }
        PRIORITY_RANK = {
            EventPriority.LOW: 1,
            EventPriority.MEDIUM: 2,
            EventPriority.HIGH: 3,
            EventPriority.CRITICAL: 4
        }
        
        if not self.observed_hazards:
            return EventType.FIRE
            
        best_hz = self.observed_hazards[0]
        best_rank = 0
        for hz in self.observed_hazards:
            p = HAZARD_PRIORITY.get(hz, EventPriority.LOW)
            r = PRIORITY_RANK.get(p, 1)
            if r > best_rank:
                best_rank = r
                best_hz = hz
        return best_hz

    @property
    def event_type(self) -> Any:
        """Alias returning primary hazard for legacy/compatibility support."""
        return self.primary_hazard

    @property
    def incident_type(self) -> Any:
        """Alias returning primary hazard for legacy/compatibility support."""
        return self.primary_hazard

    @property
    def event_id(self) -> str:
        return self.incident_id

    @property
    def timestamp(self) -> float:
        return self.start_time

    @property
    def status(self) -> Any:
        return CompatibleStatus(self._status.value, self._status)

    @status.setter
    def status(self, val: Any) -> None:
        old_status = self._status
        if isinstance(val, CompatibleStatus):
            self._status = val.state_enum
        elif isinstance(val, IncidentState):
            self._status = val
        else:
            val_str = str(val).upper()
            if val_str == "CLOSED":
                self._status = IncidentState.RESOLVED
            elif val_str in ("PROCESSING", "VERIFIED", "ACTIVE"):
                self._status = IncidentState.ACTIVE
            elif val_str == "FAILED":
                self._status = IncidentState.RESOLVED
            else:
                try:
                    self._status = IncidentState(val_str)
                except ValueError:
                    self._status = IncidentState.ACTIVE
        
        if self._status == IncidentState.RESOLVED and old_status != IncidentState.RESOLVED:
            if not getattr(self, "resolved_time", None):
                import time
                self.resolved_time = time.time()

    def add_timeline_event(self, event_name: str, timestamp: float, confidence: float, bbox: Tuple[int, int, int, int]) -> None:
        self.timeline.append({
            "event": event_name,
            "timestamp": timestamp,
            "confidence": confidence,
            "bounding_box": bbox
        })

    def __repr__(self) -> str:
        return (
            f"Incident(id={self.incident_id!r}, hazards={[h.value for h in self.observed_hazards]}, "
            f"status={self._status.value}, count={self.detection_count}, duration={self.duration:.1f}s)"
        )
