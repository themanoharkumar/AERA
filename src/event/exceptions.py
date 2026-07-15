"""Custom exceptions for the AERA Event Management System.

All exceptions in this module inherit from the base EventError class,
providing a standardized way to handle event-related issues.
"""


class EventError(Exception):
    """Base exception class for all event-related errors in AERA."""

    def __init__(self, message: str = "An event error occurred.") -> None:
        """Initialize the EventError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)
        self.message = message


class InvalidEventError(EventError):
    """Raised when an event contains invalid attribute values or structure."""

    def __init__(self, message: str = "The event structure or value is invalid.") -> None:
        """Initialize the InvalidEventError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class DuplicateEventError(EventError):
    """Raised when trying to register an event with an ID that is already registered."""

    def __init__(self, message: str = "An event with this ID already exists.") -> None:
        """Initialize the DuplicateEventError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class EventNotFoundError(EventError):
    """Raised when a requested event cannot be found in the event registry."""

    def __init__(self, message: str = "The specified event was not found.") -> None:
        """Initialize the EventNotFoundError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class EventValidationError(EventError):
    """Raised when event attributes fail validation checks (e.g. confidence score out of bounds)."""

    def __init__(self, message: str = "Event validation failed.") -> None:
        """Initialize the EventValidationError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)
