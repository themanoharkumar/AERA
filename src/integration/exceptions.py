"""Custom exceptions for the AERA System Integration layer.

All exceptions in this module inherit from the base IntegrationError class,
providing a standardized way to handle system integration and pipeline failures.
"""


class IntegrationError(Exception):
    """Base exception class for all AERA system integration errors."""

    def __init__(self, message: str) -> None:
        """Initialize the IntegrationError.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)
        self.message = message


class PipelineError(IntegrationError):
    """Raised when data propagation or step execution within the pipeline fails."""

    pass


class ValidationError(IntegrationError):
    """Raised when startup checks, interface matching, or configurations fail."""

    pass
