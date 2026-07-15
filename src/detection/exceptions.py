"""Custom exceptions for the AERA Detection Engine.

All exceptions in this module inherit from the base DetectionError class,
providing a standardized way to handle AI model and detector issues.
"""


class DetectionError(Exception):
    """Base exception class for all detection engine errors in AERA."""

    def __init__(self, message: str = "A detection error occurred.") -> None:
        """Initialize the DetectionError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)
        self.message = message


class ModelLoadError(DetectionError):
    """Raised when an AI model file or weights fail to load properly."""

    def __init__(self, message: str = "Failed to load the specified AI model.") -> None:
        """Initialize the ModelLoadError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class InferenceError(DetectionError):
    """Raised when AI model prediction or frame preprocessing fails during inference."""

    def __init__(self, message: str = "Failed to run inference on the frame.") -> None:
        """Initialize the InferenceError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class PluginRegistryError(DetectionError):
    """Raised when registering, retrieving, or unregistering detection plugins fails."""

    def __init__(self, message: str = "Detector plugin registry operation failed.") -> None:
        """Initialize the PluginRegistryError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class PluginLoadError(DetectionError):
    """Raised when a detection plugin module cannot be dynamically imported or initialized."""

    def __init__(self, message: str = "Failed to load the specified detector plugin.") -> None:
        """Initialize the PluginLoadError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)
