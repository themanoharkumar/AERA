"""AERA Decision Engine package.

This package exposes the decision layer, coordinates rule evaluation pipelines,
applies pacing configurations, and logs reasoning results.
"""

from src.decision.engine import DecisionEngine
from src.decision.exceptions import DecisionError, PolicyError, RuleExecutionError
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

__all__ = [
    "DecisionEngine",
    "DecisionPolicy",
    "DecisionResult",
    "DecisionSeverity",
    "BaseRule",
    "ConfidenceThresholdRule",
    "DuplicateSuppressionRule",
    "SeverityCalculationRule",
    "ActionDeterminationRule",
    "DecisionError",
    "RuleExecutionError",
    "PolicyError",
]
