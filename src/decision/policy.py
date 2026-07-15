"""DecisionPolicy class representing AERA Decision Engine configuration.

This module defines the DecisionPolicy class, which controls thresholds, timing,
and suppression rules during event evaluation.
"""

from typing import Any, Dict, Optional
from src.event.types import EventType


class DecisionPolicy:
    """Encapsulates configurable business rules and parameters for event analysis.

    Controls confidence filters, duplicate suppression intervals, and escalation pacing.
    """

    def __init__(
        self,
        confidence_thresholds: Optional[Dict[EventType, float]] = None,
        default_confidence_threshold: float = 0.5,
        duplicate_suppression_window: float = 60.0,
        cooldown_period: float = 300.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a new DecisionPolicy instance.

        Args:
            confidence_thresholds: Custom mapping of EventType to float confidence thresholds.
            default_confidence_threshold: Fallback threshold if an EventType is not mapped.
            duplicate_suppression_window: Max window (seconds) to suppress duplicate events.
            cooldown_period: Period in seconds to avoid redundant escalations.
            metadata: Optional dictionary for dynamic metadata or rule-specific configuration.
        """
        self.default_confidence_threshold = default_confidence_threshold
        self.confidence_thresholds = confidence_thresholds if confidence_thresholds is not None else {}
        self.duplicate_suppression_window = duplicate_suppression_window
        self.cooldown_period = cooldown_period
        self.metadata = metadata if metadata is not None else {}

    def get_confidence_threshold(self, event_type: EventType) -> float:
        """Retrieve the confidence threshold for the specified event type.

        If the event type is not configured in confidence_thresholds, returns the
        default_confidence_threshold.

        Args:
            event_type: The category of event.

        Returns:
            The confidence threshold as float.
        """
        return self.confidence_thresholds.get(event_type, self.default_confidence_threshold)
