"""Custom exceptions for the AERA Report Engine.

All exceptions in this module inherit from the base ReportError class,
providing a structured way to handle report-related issues.
"""


class ReportError(Exception):
    """Base exception class for all Report Engine errors."""

    def __init__(self, message: str) -> None:
        """Initialize the ReportError.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)
        self.message = message


class TemplateError(ReportError):
    """Raised when report layout, template rendering, or section compilation fails."""

    pass


class ExportError(ReportError):
    """Raised when serializing or exporting reports to file streams fails."""

    pass
