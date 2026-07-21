"""Event priority definitions for the AERA Event Management System.

This module defines the EventPriority enum containing all supported urgency levels.
"""

from enum import Enum


class EventPriority(str, Enum):
    """Represents the priority/urgency level of an emergency event in AERA.

    Priority Levels:
        LOW: Low urgency event (e.g., minor warning or crowd threshold limit).
        MEDIUM: Moderate urgency event requiring observation or tracking.
        HIGH: High urgency event requiring prompt response (e.g., smoke or zone intrusion).
        CRITICAL: Extremely high urgency event requiring immediate emergency action (e.g., active fire).
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
