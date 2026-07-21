"""DecisionResult definition for AERA Decision Engine.

This module defines the DecisionResult class representing the standardized output
of the Decision Engine layer.
"""

from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.decision.severity import DecisionSeverity


class DecisionResult:
    """Standardized representation of a Decision Engine reasoning outcome.

    Encapsulates decision metadata, assigned severity levels, and next step actions.
    """

    def __init__(
        self,
        decision_id: str,
        event_id: str,
        severity: "DecisionSeverity",
        action: str,
        reason: str,
        confidence: float,
        timestamp: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a new DecisionResult instance.

        Args:
            decision_id: Unique identifier for this decision.
            event_id: The identifier of the event this decision evaluates.
            severity: The assigned severity level (DecisionSeverity).
            action: The next action to take (e.g. 'escalate', 'suppress', 'cooldown').
            reason: Explanation of the business logic outcome.
            confidence: The confidence score of the decision evaluation.
            timestamp: Epoch timestamp when the decision was made.
            metadata: Optional dictionary for dynamic metadata.
        """
        self.decision_id = decision_id
        self.event_id = event_id
        self.severity = severity
        self.action = action
        self.reason = reason
        self.confidence = confidence
        self.timestamp = timestamp
        self.metadata = metadata if metadata is not None else {}

    def __repr__(self) -> str:
        """Return a string representation of the DecisionResult instance.

        Returns:
            A string format showing critical attributes of the decision result.
        """
        sev_val = getattr(self.severity, "value", str(self.severity))
        return (
            f"DecisionResult(id={self.decision_id!r}, event_id={self.event_id!r}, "
            f"severity={sev_val!r}, action={self.action!r}, "
            f"confidence={self.confidence:.2f})"
        )
