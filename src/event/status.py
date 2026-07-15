"""Event status definitions for the AERA Event Management System.

This module defines the EventStatus enum containing all stages in the lifecycle of an emergency event.
"""

from enum import Enum


class EventStatus(str, Enum):
    """Represents the lifecycle state of an emergency event in AERA.

    Statuses:
        NEW: Newly created event from raw detections, not yet analyzed.
        VERIFIED: Verified by logic or an operator as a real event.
        PROCESSING: Currently active and being handled by the emergency response workflows.
        RESOLVED: Action has been taken and the emergency situation is closed.
        FAILED: The event was found to be invalid, a false positive, or cancelled.
    """

    NEW = "NEW"
    VERIFIED = "VERIFIED"
    PROCESSING = "PROCESSING"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"
