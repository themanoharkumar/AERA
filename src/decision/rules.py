"""Modular decision rules for the AERA Decision Engine.

This module defines the BaseRule interface and concrete rule classes for evaluating
events against policies.
"""

from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List

from src.decision.policy import DecisionPolicy
from src.decision.severity import DecisionSeverity
from src.event.event import Event
from src.event.priority import EventPriority

logger = logging.getLogger(__name__)


class BaseRule(ABC):
    """Abstract base class representing a modular decision reasoning rule."""

    @abstractmethod
    def evaluate(self, event: Event, policy: DecisionPolicy, context: Dict[str, Any]) -> None:
        """Evaluate the event against the policy.

        Modifies/adds data to the context dict to accumulate reasoning outcomes.

        Args:
            event: The Event instance to evaluate.
            policy: The DecisionPolicy containing configuration values.
            context: Shared dictionary containing accumulative decision data.
        """
        pass


class ConfidenceThresholdRule(BaseRule):
    """Verifies if the event confidence meets or exceeds policy thresholds."""

    def evaluate(self, event: Event, policy: DecisionPolicy, context: Dict[str, Any]) -> None:
        """Evaluate confidence threshold.

        If event.confidence is below threshold, sets action to 'suppress' and marks
        suppressed as True.
        """
        threshold = policy.get_confidence_threshold(event.event_type)
        if event.confidence < threshold:
            context["action"] = "suppress"
            context["suppressed"] = True
            context["reason"] = (
                f"Event confidence {event.confidence:.2f} is below policy threshold {threshold:.2f}."
            )
            logger.info("Event %s suppressed due to confidence threshold.", event.event_id)


class DuplicateSuppressionRule(BaseRule):
    """Identifies and suppresses duplicate events within the suppression window."""

    def evaluate(self, event: Event, policy: DecisionPolicy, context: Dict[str, Any]) -> None:
        """Evaluate duplicate suppression against history list in context."""
        if context.get("suppressed"):
            return

        history: List[Event] = context.get("history", [])
        for past_event in history:
            if past_event.camera_id == event.camera_id and past_event.event_type == event.event_type:
                time_diff = abs(event.timestamp - past_event.timestamp)
                if time_diff <= policy.duplicate_suppression_window:
                    context["action"] = "suppress"
                    context["suppressed"] = True
                    context["reason"] = (
                        f"Duplicate event suppressed. Same event type occurred on camera {event.camera_id} "
                        f"within suppression window ({time_diff:.1f}s <= {policy.duplicate_suppression_window}s)."
                    )
                    logger.info("Event %s suppressed as duplicate of event %s.", event.event_id, past_event.event_id)
                    return


class SeverityCalculationRule(BaseRule):
    """Calculates and assigns severity based on event priority."""

    def evaluate(self, event: Event, policy: DecisionPolicy, context: Dict[str, Any]) -> None:
        """Map event priority to DecisionSeverity."""
        priority_map = {
            EventPriority.LOW: DecisionSeverity.LOW,
            EventPriority.MEDIUM: DecisionSeverity.MEDIUM,
            EventPriority.HIGH: DecisionSeverity.HIGH,
            EventPriority.CRITICAL: DecisionSeverity.CRITICAL,
        }
        context["severity"] = priority_map.get(event.priority, DecisionSeverity.LOW)


class ActionDeterminationRule(BaseRule):
    """Determines final actions (escalate, monitor, suppress, cooldown)."""

    def evaluate(self, event: Event, policy: DecisionPolicy, context: Dict[str, Any]) -> None:
        """Decide final action based on severity and cooldown timestamp."""
        if context.get("suppressed"):
            return

        severity = context.get("severity", DecisionSeverity.LOW)

        last_escalation_time = context.get("last_escalation_time", 0.0)
        if last_escalation_time > 0.0:
            time_diff = abs(event.timestamp - last_escalation_time)
            if time_diff <= policy.cooldown_period:
                context["action"] = "cooldown"
                context["reason"] = (
                    f"Action set to cooldown. Escalation suppressed to avoid alert flooding. "
                    f"Last escalation was {time_diff:.1f}s ago (cooldown period: {policy.cooldown_period}s)."
                )
                logger.info("Event %s placed in cooldown.", event.event_id)
                return

        if severity in (DecisionSeverity.HIGH, DecisionSeverity.CRITICAL):
            context["action"] = "escalate"
            context["reason"] = f"Event escalated due to high urgency severity: {severity.value}."
        else:
            context["action"] = "monitor"
            context["reason"] = f"Event action set to monitor under low urgency severity: {severity.value}."
