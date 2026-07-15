"""DecisionEngine coordination layer for AERA.

This module defines the DecisionEngine class, which coordinates event evaluation
across a modular pipeline of BaseRule implementations.
"""

import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from src.decision.exceptions import DecisionError, RuleExecutionError
from src.decision.policy import DecisionPolicy
from src.decision.result import DecisionResult
from src.decision.rules import (
    ActionDeterminationRule,
    BaseRule,
    ConfidenceThresholdRule,
    DuplicateSuppressionRule,
    SeverityCalculationRule,
)
from src.decision.severity import DecisionSeverity
from src.event.event import Event

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Coordinates and executes decision-making rules on Events.

    Maintains in-memory event history and last escalation pacing logs thread-safely
    to process events against configurable policies and return DecisionResults.
    """

    def __init__(
        self,
        policy: Optional[DecisionPolicy] = None,
        rules: Optional[List[BaseRule]] = None,
    ) -> None:
        """Initialize the DecisionEngine.

        Args:
            policy: Optional custom DecisionPolicy. Defaults to a default DecisionPolicy.
            rules: Optional list of BaseRule execution pipeline. If None, instantiates standard rules.
        """
        self.policy = policy if policy is not None else DecisionPolicy()

        # Instantiate standard pipeline if rules are not provided
        self.rules = (
            rules
            if rules is not None
            else [
                ConfidenceThresholdRule(),
                DuplicateSuppressionRule(),
                SeverityCalculationRule(),
                ActionDeterminationRule(),
            ]
        )

        self._history: List[Event] = []
        # Maps (camera_id, event_type_value) -> last escalation timestamp
        self._last_escalation_times: Dict[Tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def evaluate_event(self, event: Event) -> DecisionResult:
        """Evaluate an incoming Event against rules and policy.

        Runs the event sequentially through the rules pipeline, records it in history,
        manages pacing timelines, and produces a final DecisionResult.

        Args:
            event: The Event instance to analyze.

        Returns:
            The generated DecisionResult object.

        Raises:
            DecisionError: If evaluation fails or parameter is invalid.
        """
        if event is None:
            raise DecisionError("Event cannot be None.")

        with self._lock:
            # Build evaluation context
            context: Dict[str, Any] = {
                "history": list(self._history),
                "last_escalation_time": self._last_escalation_times.get(
                    (event.camera_id, event.event_type.value), 0.0
                ),
                "suppressed": False,
                "action": "monitor",
                "severity": DecisionSeverity.LOW,
                "reason": "Initial state.",
            }

            # Execute the rule pipeline
            for rule in self.rules:
                try:
                    rule.evaluate(event, self.policy, context)
                except Exception as e:
                    logger.exception("Error executing rule %s on event %s", rule.__class__.__name__, event.event_id)
                    raise RuleExecutionError(f"Rule {rule.__class__.__name__} execution failed: {e}") from e

            # Generate standardized result
            result = DecisionResult(
                decision_id=str(uuid.uuid4()),
                event_id=event.event_id,
                severity=context["severity"],
                action=context["action"],
                reason=context["reason"],
                confidence=event.confidence,
                timestamp=time.time(),
                metadata={
                    "policy_duplicate_suppression_window": self.policy.duplicate_suppression_window,
                    "policy_cooldown_period": self.policy.cooldown_period,
                    "camera_id": event.camera_id,
                    "event_type": event.event_type.value,
                },
            )

            # Record event in thread-safe history cache
            self._history.append(event)

            # Record escalation pacing state
            if context["action"] == "escalate":
                self._last_escalation_times[(event.camera_id, event.event_type.value)] = event.timestamp

            return result

    def get_history(self) -> List[Event]:
        """Get a copy of the processed event history cache.

        Returns:
            A list of Event instances.
        """
        with self._lock:
            return list(self._history)

    def clear(self) -> None:
        """Clear all event history cache and escalation logs."""
        with self._lock:
            self._history.clear()
            self._last_escalation_times.clear()
            logger.info("DecisionEngine history cleared.")
