"""Custom exceptions for the AERA Alert System.

All exceptions in this module inherit from the base AlertError class,
providing a standardized way to handle alert-related issues.
"""


class AlertError(Exception):
    """Base exception class for all Alert System errors."""

    def __init__(self, message: str) -> None:
        """Initialize the AlertError.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)
        self.message = message


class NotificationError(AlertError):
    """Raised when validating payloads or delivering notifications fails."""

    pass


class ChannelError(AlertError):
    """Raised when channel registration, activation, or configuration fails."""

    pass
