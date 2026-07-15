"""Custom exceptions for the AERA Decision Engine.

All exceptions in this module inherit from the base DecisionError class,
providing a standardized way to handle decision-related issues.
"""


class DecisionError(Exception):
    """Base exception class for all Decision Engine errors."""

    def __init__(self, message: str) -> None:
        """Initialize the DecisionError.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)
        self.message = message


class RuleExecutionError(DecisionError):
    """Raised when a business rule fails during evaluation or execution."""

    pass


class PolicyError(DecisionError):
    """Raised when a decision policy configuration is invalid or violated."""

    pass
