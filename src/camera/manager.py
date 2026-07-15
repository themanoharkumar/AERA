"""CameraManager class implementation for the AERA Camera Management System.

This module provides the central coordinating CameraManager class, which manages
the registry of Camera entities and their active CameraStream instances.
"""

import logging
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from .camera import Camera, CameraStatus
from .exceptions import (
    CameraAlreadyExistsError,
    CameraConnectionError,
    CameraInitializationError,
    CameraNotFoundError,
    CameraOfflineError,
)
from .stream import CameraStream

logger = logging.getLogger(__name__)


class CameraManager:
    """Manages discovery, registration, control, and frame routing for all cameras.

    This class coordinates lightweight Camera entities with their active CameraStream
    connections. It protects shared registry resources via a threading lock.
    """

    def __init__(self) -> None:
        """Initialize the CameraManager."""
        self._cameras: Dict[str, Camera] = {}
        self._streams: Dict[str, CameraStream] = {}
        self._lock = threading.Lock()
        logger.info("CameraManager initialized.")

    def register_camera(
        self,
        camera_id: str,
        name: str,
        source: Union[int, str],
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Camera:
        """Register a new camera in the system.

        Args:
            camera_id: Unique identifier for the camera.
            name: Human-readable name.
            source: Source index (USB) or URL (RTSP/file).
            config: Configuration parameters (e.g. resolution, frame_rate).
            metadata: Custom metadata dictionary.

        Returns:
            The registered Camera entity.

        Raises:
            CameraAlreadyExistsError: If a camera is already registered with camera_id.
        """
        with self._lock:
            if camera_id in self._cameras:
                logger.error("Registration failed: Camera ID '%s' already exists.", camera_id)
                raise CameraAlreadyExistsError(
                    f"A camera with ID '{camera_id}' is already registered."
                )

            logger.info("Registering camera: ID='%s', Name='%s', Source='%s'", camera_id, name, source)
            camera = Camera(
                camera_id=camera_id,
                name=name,
                source=source,
                config=config,
                metadata=metadata,
            )
            stream = CameraStream(source=source, config=camera.config)

            self._cameras[camera_id] = camera
            self._streams[camera_id] = stream

            logger.info("Successfully registered camera '%s' with status REGISTERED.", camera_id)
            return camera

    def remove_camera(self, camera_id: str) -> None:
        """Stop, disconnect, and remove a camera from the registry.

        Args:
            camera_id: Unique identifier of the camera to remove.

        Raises:
            CameraNotFoundError: If no camera exists with camera_id.
        """
        # Ensure cleanup is done outside registry lock to prevent deadlock with capture threads
        stream_to_disconnect: Optional[CameraStream] = None

        with self._lock:
            if camera_id not in self._cameras:
                logger.error("Removal failed: Camera ID '%s' not found.", camera_id)
                raise CameraNotFoundError(f"Camera with ID '{camera_id}' does not exist.")

            logger.info("Removing camera '%s' from registry.", camera_id)
            stream_to_disconnect = self._streams[camera_id]
            del self._cameras[camera_id]
            del self._streams[camera_id]

        if stream_to_disconnect is not None:
            try:
                stream_to_disconnect.disconnect()
            except Exception as e:
                logger.error("Error disconnecting stream during removal of camera '%s': %s", camera_id, e)

        logger.info("Successfully removed camera '%s'.", camera_id)

    def start_camera(self, camera_id: str) -> None:
        """Connect and start streaming frames from the specified camera.

        Args:
            camera_id: Unique identifier of the camera to start.

        Raises:
            CameraNotFoundError: If no camera exists with camera_id.
            CameraConnectionError: If connection fails.
            CameraInitializationError: If setup fails.
        """
        camera: Optional[Camera] = None
        stream: Optional[CameraStream] = None

        with self._lock:
            if camera_id not in self._cameras:
                logger.error("Start failed: Camera ID '%s' not found.", camera_id)
                raise CameraNotFoundError(f"Camera with ID '{camera_id}' does not exist.")

            camera = self._cameras[camera_id]
            stream = self._streams[camera_id]

            if camera.status == CameraStatus.STREAMING:
                logger.warning("Camera '%s' is already streaming.", camera_id)
                return

            logger.info("Starting camera '%s'. Transitioning status to CONNECTING.", camera_id)
            camera.status = CameraStatus.CONNECTING

        try:
            # Connect the stream (OpenCV)
            stream.connect()

            with self._lock:
                camera.status = CameraStatus.CONNECTED
                logger.info("Camera '%s' connected. Transitioning status to CONNECTED.", camera_id)

            # Start background thread frame reading
            stream.start_stream()

            with self._lock:
                camera.status = CameraStatus.STREAMING
                logger.info("Camera '%s' streaming. Transitioning status to STREAMING.", camera_id)

        except (CameraConnectionError, CameraInitializationError) as e:
            with self._lock:
                camera.status = CameraStatus.DISCONNECTED
            logger.error("Failed to start camera '%s': %s", camera_id, e)
            raise
        except Exception as e:
            with self._lock:
                camera.status = CameraStatus.DISCONNECTED
            logger.exception("Unexpected failure when starting camera '%s': %s", camera_id, e)
            raise CameraInitializationError(f"Unexpected error starting camera '{camera_id}': {e}") from e

    def stop_camera(self, camera_id: str) -> None:
        """Stop streaming and disconnect the specified camera.

        Args:
            camera_id: Unique identifier of the camera to stop.

        Raises:
            CameraNotFoundError: If no camera exists with camera_id.
        """
        camera: Optional[Camera] = None
        stream: Optional[CameraStream] = None

        with self._lock:
            if camera_id not in self._cameras:
                logger.error("Stop failed: Camera ID '%s' not found.", camera_id)
                raise CameraNotFoundError(f"Camera with ID '{camera_id}' does not exist.")

            camera = self._cameras[camera_id]
            stream = self._streams[camera_id]

        logger.info("Stopping camera '%s'.", camera_id)
        try:
            stream.disconnect()
        finally:
            with self._lock:
                camera.status = CameraStatus.DISCONNECTED
                logger.info("Camera '%s' stopped. Transitioning status to DISCONNECTED.", camera_id)

    def restart_camera(self, camera_id: str) -> None:
        """Stop and restart the specified camera stream.

        Args:
            camera_id: Unique identifier of the camera to restart.

        Raises:
            CameraNotFoundError: If no camera exists with camera_id.
        """
        logger.info("Restarting camera '%s'.", camera_id)
        self.stop_camera(camera_id)
        self.start_camera(camera_id)

    def get_frame(self, camera_id: str) -> Tuple[float, Optional[np.ndarray]]:
        """Retrieve the latest frame and timestamp from the camera stream.

        Args:
            camera_id: Unique identifier of the camera.

        Returns:
            A tuple of (timestamp: float, frame: Optional[np.ndarray]).

        Raises:
            CameraNotFoundError: If no camera exists with camera_id.
            CameraOfflineError: If the camera is not actively streaming.
        """
        camera: Optional[Camera] = None
        stream: Optional[CameraStream] = None

        with self._lock:
            if camera_id not in self._cameras:
                raise CameraNotFoundError(f"Camera with ID '{camera_id}' does not exist.")

            camera = self._cameras[camera_id]
            stream = self._streams[camera_id]

            if camera.status != CameraStatus.STREAMING:
                logger.error("Failed to get frame: Camera '%s' is not streaming. Current status: %s", camera_id, camera.status.value)
                raise CameraOfflineError(
                    f"Camera '{camera_id}' is offline/not streaming (status: {camera.status.value})."
                )

        return stream.read_frame()

    def list_cameras(self) -> List[Camera]:
        """List all registered cameras.

        Returns:
            A list of Camera entities copy to avoid external mutations.
        """
        with self._lock:
            return list(self._cameras.values())

    def camera_status(self, camera_id: str) -> CameraStatus:
        """Retrieve the current operational status of the camera.

        Args:
            camera_id: Unique identifier of the camera.

        Returns:
            The current CameraStatus.

        Raises:
            CameraNotFoundError: If no camera exists with camera_id.
        """
        with self._lock:
            if camera_id not in self._cameras:
                raise CameraNotFoundError(f"Camera with ID '{camera_id}' does not exist.")
            return self._cameras[camera_id].status

    def shutdown(self) -> None:
        """Stop and release all registered camera streams."""
        logger.info("Shutting down CameraManager. Releasing all camera resources.")
        camera_ids = []
        with self._lock:
            camera_ids = list(self._cameras.keys())

        for camera_id in camera_ids:
            try:
                self.stop_camera(camera_id)
            except Exception as e:
                logger.error("Error stopping camera '%s' during shutdown: %s", camera_id, e)
