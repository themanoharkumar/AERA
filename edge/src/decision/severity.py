"""DecisionSeverity enum definitions for AERA Decision Engine.

This module defines the DecisionSeverity enum representing the severity classification
assigned by decision policies to evaluated events.
"""

from enum import Enum


class DecisionSeverity(Enum):
    """Represents the severity level of a decision.

    Used to determine escalation logic, priority handling, and response timing.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
