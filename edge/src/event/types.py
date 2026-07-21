"""Event type definitions for the AERA Event Management System.

This module defines the EventType enum containing all supported AI detection event categories.
"""

from enum import Enum


class EventType(str, Enum):
    """Represents the category of an emergency event in AERA.

    Event Types:
        FIRE: Fire emergency situations.
        SMOKE: Smoke or potential fire hazards.
        FALL: Human fall detection incidents.
        VIOLENCE: Suspicious physical violence or fighting.
        INTRUSION: Unauthorized entry into restricted zones.
        CROWD: High-density crowd or congestion situations.
    """

    FIRE = "FIRE"
    SMOKE = "SMOKE"
    FALL = "FALL"
    VIOLENCE = "VIOLENCE"
    INTRUSION = "INTRUSION"
    CROWD = "CROWD"
