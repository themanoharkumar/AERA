"""Event manager definition for the AERA Event Management System.

This module defines the EventManager class, providing thread-safe CRUD,
validation, lifecycle management, and filtering of standardized events.
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Union
import uuid

from src.event.event import Event
from src.event.exceptions import (
    DuplicateEventError,
    EventNotFoundError,
    EventValidationError,
)
from src.event.priority import EventPriority
from src.event.status import EventStatus
from src.event.types import EventType

logger = logging.getLogger(__name__)


class EventManager:
    """Orchestrates event registration, updates, and querying.

    Provides a thread-safe registry mapping event IDs to Event entities,
    performing validations on event states, confidence limits, and type categories.
    """

    def __init__(self) -> None:
        """Initialize the EventManager with an empty registry."""
        self._events: Dict[str, Event] = {}
        self._lock = threading.Lock()

    def _validate_confidence(self, confidence: float) -> None:
        """Validate that the confidence score is within [0.0, 1.0].

        Args:
            confidence: The confidence score to validate.

        Raises:
            EventValidationError: If the confidence is out of bounds.
        """
        if not isinstance(confidence, (int, float)):
            raise EventValidationError("Confidence score must be a number.")
        if not (0.0 <= confidence <= 1.0):
            raise EventValidationError(
                f"Confidence score {confidence} is out of bounds [0.0, 1.0]."
            )

    def _validate_enums(
        self,
        event_type: Union[str, EventType],
        priority: Union[str, EventPriority],
        status: Union[str, EventStatus],
    ) -> tuple[EventType, EventPriority, EventStatus]:
        """Validate and convert input values to their respective enum classes.

        Args:
            event_type: The event type.
            priority: The event priority.
            status: The event status.

        Returns:
            A tuple of (EventType, EventPriority, EventStatus).

        Raises:
            EventValidationError: If any of the inputs cannot be converted.
        """
        try:
            val_type = EventType(event_type)
        except ValueError:
            raise EventValidationError(f"Invalid event type: {event_type}")

        try:
            val_priority = EventPriority(priority)
        except ValueError:
            raise EventValidationError(f"Invalid priority level: {priority}")

        try:
            val_status = EventStatus(status)
        except ValueError:
            raise EventValidationError(f"Invalid status state: {status}")

        return val_type, val_priority, val_status

    def create_event(
        self,
        event_type: Union[str, EventType],
        camera_id: str,
        description: str,
        confidence: float,
        priority: Union[str, EventPriority] = EventPriority.LOW,
        metadata: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> Event:
        """Create, validate, register, and return a new Event.

        Args:
            event_type: Category of the event.
            camera_id: Identifier of the camera source.
            description: Description of the event.
            confidence: Confidence score between 0.0 and 1.0.
            priority: Priority level of the event. Defaults to LOW.
            metadata: Optional dictionary for dynamic metadata.
            event_id: Optional unique identifier. If not provided, a UUID is generated.
            timestamp: Optional epoch timestamp. If not provided, current time is used.

        Returns:
            The registered Event object.

        Raises:
            EventValidationError: If validation checks fail.
            DuplicateEventError: If an event with the generated or provided ID exists.
        """
        # Validate confidence limits
        self._validate_confidence(confidence)

        # Validate and convert enums
        val_type, val_priority, val_status = self._validate_enums(
            event_type, priority, EventStatus.NEW
        )

        if not camera_id:
            raise EventValidationError("Camera ID cannot be empty.")

        # Assign defaults
        final_id = event_id if event_id is not None else str(uuid.uuid4())
        final_timestamp = timestamp if timestamp is not None else time.time()

        event = Event(
            event_id=final_id,
            event_type=val_type,
            camera_id=camera_id,
            timestamp=final_timestamp,
            priority=val_priority,
            status=val_status,
            confidence=float(confidence),
            description=description,
            metadata=metadata,
        )

        self.register_event(event)
        return event

    def register_event(self, event: Event) -> None:
        """Register an existing Event object in the registry.

        Args:
            event: The Event instance to register.

        Raises:
            DuplicateEventError: If an event with the same ID is already registered.
            EventValidationError: If the event fields fail validation checks.
        """
        if not event.event_id:
            raise EventValidationError("Event ID cannot be empty.")

        # Validate event attributes
        self._validate_confidence(event.confidence)
        self._validate_enums(event.event_type, event.priority, event.status)

        with self._lock:
            if event.event_id in self._events:
                raise DuplicateEventError(
                    f"Event with ID '{event.event_id}' is already registered."
                )
            self._events[event.event_id] = event

        logger.info("Successfully registered event: %s", event)

    def update_event(self, event_id: str, /, **kwargs: Any) -> Event:
        """Update fields of an existing event.

        Supported update fields are: priority, status, confidence, description, metadata.
        Identity attributes (event_id, event_type, camera_id, timestamp) are immutable.

        Args:
            event_id: The ID of the event to update.
            **kwargs: Key-value pairs of attributes to update.

        Returns:
            The updated Event object.

        Raises:
            EventNotFoundError: If the event cannot be found.
            EventValidationError: If attempt to update immutable fields or invalid values.
        """
        # Check for immutable modifications
        immutable_fields = {"event_id", "event_type", "camera_id", "timestamp"}
        attempted_immutables = immutable_fields.intersection(kwargs.keys())
        if attempted_immutables:
            raise EventValidationError(
                f"Cannot update immutable event fields: {list(attempted_immutables)}"
            )

        with self._lock:
            event = self._events.get(event_id)
            if event is None:
                raise EventNotFoundError(f"Event with ID '{event_id}' not found.")

            # Validate proposed values
            new_priority = kwargs.get("priority", event.priority)
            new_status = kwargs.get("status", event.status)
            new_confidence = kwargs.get("confidence", event.confidence)

            self._validate_confidence(new_confidence)
            val_type, val_priority, val_status = self._validate_enums(
                event.event_type, new_priority, new_status
            )

            # Apply changes
            if "priority" in kwargs:
                event.priority = val_priority
            if "status" in kwargs:
                event.status = val_status
            if "confidence" in kwargs:
                event.confidence = float(new_confidence)
            if "description" in kwargs:
                event.description = kwargs["description"]
            if "metadata" in kwargs:
                event.metadata = kwargs["metadata"]

        logger.info("Successfully updated event ID '%s'", event_id)
        return event

    def delete_event(self, event_id: str) -> None:
        """Remove an event from the registry.

        Args:
            event_id: The ID of the event to delete.

        Raises:
            EventNotFoundError: If the event cannot be found.
        """
        with self._lock:
            if event_id not in self._events:
                raise EventNotFoundError(f"Event with ID '{event_id}' not found.")
            del self._events[event_id]

        logger.info("Successfully deleted event ID '%s'", event_id)

    def get_event(self, event_id: str) -> Event:
        """Retrieve a registered event by its ID.

        Args:
            event_id: Unique identifier of the event.

        Returns:
            The Event instance.

        Raises:
            EventNotFoundError: If the event cannot be found.
        """
        with self._lock:
            event = self._events.get(event_id)
            if event is None:
                raise EventNotFoundError(f"Event with ID '{event_id}' not found.")
            return event

    def list_events(self) -> List[Event]:
        """List all currently registered events, sorted by timestamp descending.

        Returns:
            A list of all Event instances.
        """
        with self._lock:
            all_events = list(self._events.values())
        return sorted(all_events, key=lambda e: e.timestamp, reverse=True)

    def search_events(self, filters: Optional[Dict[str, Any]] = None) -> List[Event]:
        """Search and filter registered events.

        Args:
            filters: Dictionary of filter criteria. Supported keys:
                - 'event_type': EventType or str, or a list of them.
                - 'camera_id': str or list of str.
                - 'priority': EventPriority or str, or a list of them.
                - 'status': EventStatus or str, or a list of them.
                - 'min_confidence': float.
                - 'start_time': float (timestamp >= start_time).
                - 'end_time': float (timestamp <= end_time).

        Returns:
            A list of events matching all criteria, sorted by timestamp descending.
        """
        if filters is None:
            return self.list_events()

        matched_events: List[Event] = []

        with self._lock:
            all_events = list(self._events.values())

        for event in all_events:
            # 1. Filter by event_type
            if "event_type" in filters:
                type_filter = filters["event_type"]
                if isinstance(type_filter, (list, tuple, set)):
                    if event.event_type not in type_filter and event.event_type.value not in type_filter:
                        continue
                else:
                    if event.event_type != type_filter and event.event_type.value != type_filter:
                        continue

            # 2. Filter by camera_id
            if "camera_id" in filters:
                cam_filter = filters["camera_id"]
                if isinstance(cam_filter, (list, tuple, set)):
                    if event.camera_id not in cam_filter:
                        continue
                else:
                    if event.camera_id != cam_filter:
                        continue

            # 3. Filter by priority
            if "priority" in filters:
                priority_filter = filters["priority"]
                if isinstance(priority_filter, (list, tuple, set)):
                    if event.priority not in priority_filter and event.priority.value not in priority_filter:
                        continue
                else:
                    if event.priority != priority_filter and event.priority.value != priority_filter:
                        continue

            # 4. Filter by status
            if "status" in filters:
                status_filter = filters["status"]
                if isinstance(status_filter, (list, tuple, set)):
                    if event.status not in status_filter and event.status.value not in status_filter:
                        continue
                else:
                    if event.status != status_filter and event.status.value != status_filter:
                        continue

            # 5. Filter by min_confidence
            if "min_confidence" in filters:
                min_conf = filters["min_confidence"]
                if event.confidence < min_conf:
                    continue

            # 6. Filter by start_time
            if "start_time" in filters:
                if event.timestamp < filters["start_time"]:
                    continue

            # 7. Filter by end_time
            if "end_time" in filters:
                if event.timestamp > filters["end_time"]:
                    continue

            matched_events.append(event)

        return sorted(matched_events, key=lambda e: e.timestamp, reverse=True)

    def update_status(self, event_id: str, status: Union[str, EventStatus]) -> Event:
        """Update the lifecycle status of an event.

        Args:
            event_id: The ID of the event to update.
            status: The new EventStatus.

        Returns:
            The updated Event object.
        """
        return self.update_event(event_id, status=status)

    def update_priority(self, event_id: str, priority: Union[str, EventPriority]) -> Event:
        """Update the priority level of an event.

        Args:
            event_id: The ID of the event to update.
            priority: The new EventPriority level.

        Returns:
            The updated Event object.
        """
        return self.update_event(event_id, priority=priority)

    def clear_events(self) -> None:
        """Remove all events from the registry."""
        with self._lock:
            self._events.clear()
        logger.info("Successfully cleared event manager registry.")
