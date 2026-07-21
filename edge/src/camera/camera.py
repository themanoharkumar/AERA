"""Camera entity and status definitions for the AERA Camera Management System.

This module defines the camera status enum and the lightweight Camera data class
representing camera identity, configurations, and status without synchronization locks.
"""

from enum import Enum
from typing import Any, Dict, Optional, Union


class CameraStatus(str, Enum):
    """Represents the operational status of a camera in the AERA platform.

    Statuses:
        REGISTERED: Camera is registered in the system but not yet connected.
        CONNECTING: Transition status while initiating connection to the source.
        CONNECTED: Connection established successfully, but not streaming frames.
        STREAMING: Active stream pulling frames from the source.
        DISCONNECTED: Explicitly stopped or connection lost.
        RECONNECTING: System is trying to re-establish a lost connection.
    """

    REGISTERED = "registered"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


class Camera:
    """Lightweight representation of a camera entity in the system.

    This class maintains camera identity, source details, configuration parameters,
    and metadata. It does not handle streaming logic or thread synchronization.
    """

    def __init__(
        self,
        camera_id: str,
        name: str,
        source: Union[int, str],
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a new Camera instance.

        Args:
            camera_id: Unique identifier for the camera.
            name: Human-readable name/label for the camera.
            source: Stream source. Integer for local USB/webcam index, or
                string for RTSP URLs or video file paths.
            config: Optional configuration dictionary (e.g., target FPS, resolution).
            metadata: Optional dictionary for extra dynamic/static metadata.
        """
        self.camera_id = camera_id
        self.name = name
        self.source = source
        # TODO: Future versions may replace this dictionary with a structured CameraConfig class.
        self.config = config if config is not None else {}
        # TODO: Future versions may replace this dictionary with a structured CameraStatistics class.
        self.metadata = metadata if metadata is not None else {}
        self.status = CameraStatus.REGISTERED

    def __repr__(self) -> str:
        """Return a string representation of the Camera instance.

        Returns:
            A string format showing critical attributes of the camera.
        """
        return (
            f"Camera(id={self.camera_id!r}, name={self.name!r}, "
            f"source={self.source!r}, status={self.status.value})"
        )
