"""Custom exceptions for the AERA Evidence Management System.

All exceptions in this module inherit from the base EvidenceError class,
providing a standardized way to handle evidence-related issues.
"""


class EvidenceError(Exception):
    """Base exception class for all Evidence Management System errors."""

    def __init__(self, message: str) -> None:
        """Initialize the EvidenceError.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)
        self.message = message


class StorageError(EvidenceError):
    """Raised when file writes, directory setups, or file updates fail."""

    pass


class ValidationError(EvidenceError):
    """Raised when validation checks (missing keys, paths, schema rules) fail."""

    pass
