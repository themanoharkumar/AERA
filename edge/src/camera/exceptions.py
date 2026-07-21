"""Custom exceptions for the AERA Camera Management System.

All exceptions in this module inherit from the base CameraError class,
providing a standardized way to handle camera-related issues.
"""


class CameraError(Exception):
    """Base exception class for all camera-related errors in AERA."""

    def __init__(self, message: str = "A camera error occurred.") -> None:
        """Initialize the CameraError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)
        self.message = message


class CameraConnectionError(CameraError):
    """Raised when connection to a camera source fails or is interrupted."""

    def __init__(self, message: str = "Failed to connect to the camera source.") -> None:
        """Initialize the CameraConnectionError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class CameraNotFoundError(CameraError):
    """Raised when a specified camera is not found in the manager."""

    def __init__(self, message: str = "The specified camera was not found.") -> None:
        """Initialize the CameraNotFoundError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class CameraAlreadyExistsError(CameraError):
    """Raised when trying to register a camera with an ID that is already registered."""

    def __init__(self, message: str = "A camera with this ID already exists.") -> None:
        """Initialize the CameraAlreadyExistsError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class InvalidCameraSourceError(CameraError):
    """Raised when the provided camera source (e.g., invalid URI or index) is invalid."""

    def __init__(self, message: str = "The provided camera source is invalid.") -> None:
        """Initialize the InvalidCameraSourceError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class FrameReadError(CameraError):
    """Raised when a frame cannot be read from the camera stream."""

    def __init__(self, message: str = "Failed to read frame from the camera stream.") -> None:
        """Initialize the FrameReadError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class CameraTimeoutError(CameraError):
    """Raised when frame acquisition times out."""

    def __init__(self, message: str = "Camera operation timed out.") -> None:
        """Initialize the CameraTimeoutError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class CameraOfflineError(CameraError):
    """Raised when trying to perform operations on an offline camera."""

    def __init__(self, message: str = "The camera is currently offline.") -> None:
        """Initialize the CameraOfflineError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)


class CameraInitializationError(CameraError):
    """Raised when initializing the camera hardware or stream library fails."""

    def __init__(self, message: str = "Failed to initialize the camera.") -> None:
        """Initialize the CameraInitializationError exception.

        Args:
            message: Explanation of the error.
        """
        super().__init__(message)
