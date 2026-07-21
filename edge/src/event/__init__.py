"""AERA Event Management System package.

This package exposes the core elements of the event system, including the EventManager,
Event entity, enums for types, status, priority, and custom exceptions.
"""

from src.event.event import Event
from src.event.exceptions import (
    DuplicateEventError,
    EventError,
    EventNotFoundError,
    EventValidationError,
    InvalidEventError,
)
from src.event.manager import EventManager
from src.event.priority import EventPriority
from src.event.status import EventStatus
from src.event.types import EventType

__all__ = [
    "Event",
    "EventManager",
    "EventType",
    "EventPriority",
    "EventStatus",
    "EventError",
    "InvalidEventError",
    "DuplicateEventError",
    "EventNotFoundError",
    "EventValidationError",
]
