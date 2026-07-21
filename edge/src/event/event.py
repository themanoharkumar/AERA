"""Event entity definitions for the AERA Event Management System.

This module defines the Event class representing a standardized event model
containing emergency incident business data.
"""

from typing import Any, Dict, Optional
from src.event.priority import EventPriority
from src.event.status import EventStatus
from src.event.types import EventType


class Event:
    """Represents a standardized emergency event in the AERA platform.

    An Event object contains the business data describing a detected incident.
    It does not contain execution logic for camera reading, AI running, database
    persistence, reporting, or alerting.
    """

    def __init__(
        self,
        event_id: str,
        event_type: EventType,
        camera_id: str,
        timestamp: float,
        priority: EventPriority,
        status: EventStatus,
        confidence: float,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a new Event instance.

        Args:
            event_id: Unique identifier for the event (typically UUID).
            event_type: The category of the detected event (EventType).
            camera_id: The identifier of the camera source that generated the event.
            timestamp: Epoch timestamp when the event occurred.
            priority: The urgency level of the event (EventPriority).
            status: The lifecycle state of the event (EventStatus).
            confidence: Confidence score of the detection (float between 0.0 and 1.0).
            description: Human-readable explanation of the event.
            metadata: Optional dictionary for extra dynamic metadata.
        """
        self.event_id = event_id
        self.event_type = event_type
        self.camera_id = camera_id
        self.timestamp = timestamp
        self.priority = priority
        self.status = status
        self.confidence = confidence
        self.description = description
        self.metadata = metadata if metadata is not None else {}

    def __repr__(self) -> str:
        """Return a string representation of the Event instance.

        Returns:
            A string format showing critical attributes of the event.
        """
        return (
            f"Event(id={self.event_id!r}, type={self.event_type.value!r}, "
            f"camera_id={self.camera_id!r}, priority={self.priority.value!r}, "
            f"status={self.status.value!r}, confidence={self.confidence:.2f})"
        )
