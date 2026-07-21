"""Custom exceptions for the AERA notification subsystem."""

class NotificationException(Exception):
    """Base exception for all notification-related errors."""
    pass


class NotificationDeliveryError(NotificationException):
    """Raised when a notifier channel fails to deliver a message."""
    pass


class NotificationValidationError(NotificationException):
    """Raised when data models or payloads fail structural validation checks."""
    pass


class NotificationConfigError(NotificationException):
    """Raised when configuration variables or credentials are invalid or missing."""
    pass
