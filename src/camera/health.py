"""Camera health monitoring for the AERA Camera Management System.

This module provides the CameraHealthMonitor class, which runs a background thread
to periodically audit the status, frame rate, timeout status, and content freeze
state of all registered camera streams.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

import numpy as np

from .camera import CameraStatus
from .manager import CameraManager

logger = logging.getLogger(__name__)


class CameraHealthMonitor:
    """Monitors the health of registered cameras in the CameraManager.

    Performs periodic health audits checking for frame rate drop, connection
    timeouts, and frozen video feeds. If a camera becomes unhealthy, it triggers
    reconnection/restarts.
    """

    def __init__(
        self,
        manager: CameraManager,
        check_interval: float = 2.0,
        timeout_threshold: float = 5.0,
        max_reconnect_attempts: int = 3,
    ) -> None:
        """Initialize the CameraHealthMonitor.

        Args:
            manager: The CameraManager instance to monitor.
            check_interval: Delay in seconds between periodic health checks.
            timeout_threshold: Max seconds allowed without a new frame before timeout.
            max_reconnect_attempts: Max reconnection attempts before marking offline permanently.
        """
        self.manager = manager
        self.check_interval = check_interval
        self.timeout_threshold = timeout_threshold
        self.max_reconnect_attempts = max_reconnect_attempts

        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Track health stats
        self._last_timestamps: Dict[str, float] = {}
        self._last_frame_counts: Dict[str, int] = {}
        self._last_frames: Dict[str, np.ndarray] = {}
        self._freeze_counts: Dict[str, int] = {}
        self._reconnect_attempts: Dict[str, int] = {}

    def start(self) -> None:
        """Start the background health monitoring thread."""
        with self._lock:
            if self._running:
                logger.warning("CameraHealthMonitor is already running.")
                return

            self._running = True
            self._thread = threading.Thread(
                target=self._monitor_loop,
                name="CameraHealthMonitorThread",
                daemon=True,
            )
            self._thread.start()
            logger.info("CameraHealthMonitor started.")

    def stop(self) -> None:
        """Stop the background health monitoring thread."""
        logger.info("Stopping CameraHealthMonitor.")
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("CameraHealthMonitor stopped.")

    def _monitor_loop(self) -> None:
        """Periodic loop auditing active streams."""
        while self._running:
            try:
                time.sleep(self.check_interval)
                self._check_cameras()
            except Exception as e:
                logger.exception("Error in CameraHealthMonitor check cycle: %s", e)

    def _check_cameras(self) -> None:
        """Perform health checks on all registered cameras."""
        cameras = self.manager.list_cameras()

        for camera in cameras:
            camera_id = camera.camera_id
            status = camera.status

            # We only monitor cameras that are supposed to be streaming or reconnecting
            if status not in (CameraStatus.STREAMING, CameraStatus.RECONNECTING):
                # Clean up tracking dictionary keys for inactive cameras
                self._cleanup_camera_tracking(camera_id)
                continue

            # Retrieve internal stream object
            # Note: Accessing internal _streams is safe inside the package
            stream = self.manager._streams.get(camera_id)
            if stream is None:
                logger.warning("Stream object missing for registered camera '%s'", camera_id)
                self._handle_unhealthy(camera_id, "Missing stream object")
                continue

            if not stream.is_connected():
                self._handle_unhealthy(camera_id, "Stream disconnected")
                continue

            # Read latest timestamp and frame
            timestamp, frame = stream.read_frame()

            # Retrieve frame count if available (for FPS calculation)
            frame_count = getattr(stream, "frame_count", 0)

            # 1. Timeout Check
            current_time = time.time()
            last_timestamp = self._last_timestamps.get(camera_id, timestamp)

            if timestamp == 0.0 or frame is None:
                # Stream has started but no frame received yet
                # Check connection age or wait a cycle
                self._last_timestamps[camera_id] = current_time
                self._last_frame_counts[camera_id] = frame_count
                continue

            time_since_last_frame = current_time - timestamp
            if time_since_last_frame > self.timeout_threshold:
                self._handle_unhealthy(
                    camera_id,
                    f"Frame timeout (no frame for {time_since_last_frame:.1f}s)",
                )
                continue

            # 2. Frozen Stream Check
            # Check if frame timestamp changed. If it didn't, it is covered by timeout.
            # If the timestamp DID change, check if the frame pixels are identical.
            is_frozen = False
            if camera_id in self._last_frames and timestamp != last_timestamp:
                prev_frame = self._last_frames[camera_id]
                if np.array_equal(frame, prev_frame):
                    self._freeze_counts[camera_id] = self._freeze_counts.get(camera_id, 0) + 1
                    logger.warning(
                        "Camera '%s' detected identical frame content (Freeze count: %d)",
                        camera_id,
                        self._freeze_counts[camera_id],
                    )
                    # If stream content is identical for 5 consecutive checks, flag frozen
                    if self._freeze_counts[camera_id] >= 5:
                        is_frozen = True
                else:
                    self._freeze_counts[camera_id] = 0

            if is_frozen:
                self._handle_unhealthy(camera_id, "Frozen frame content detected")
                continue

            # 3. FPS Monitoring
            last_fc = self._last_frame_counts.get(camera_id, frame_count)
            frames_read = frame_count - last_fc
            measured_fps = frames_read / self.check_interval

            # Store stats for metadata updates
            camera.metadata["measured_fps"] = measured_fps
            camera.metadata["last_frame_time"] = timestamp

            # Reset reconnect count on successful health check
            if status == CameraStatus.STREAMING and measured_fps > 0:
                self._reconnect_attempts[camera_id] = 0

            # Update cache
            self._last_timestamps[camera_id] = timestamp
            self._last_frame_counts[camera_id] = frame_count
            self._last_frames[camera_id] = frame.copy()

    def _handle_unhealthy(self, camera_id: str, reason: str) -> None:
        """Trigger recovery or mark camera as disconnected based on health audit.

        Args:
            camera_id: Unique identifier of the unhealthy camera.
            reason: Description of the health failure.
        """
        logger.error("Camera '%s' is unhealthy. Reason: %s", camera_id, reason)

        attempts = self._reconnect_attempts.get(camera_id, 0)
        if attempts < self.max_reconnect_attempts:
            self._reconnect_attempts[camera_id] = attempts + 1
            logger.info(
                "Attempting reconnection for camera '%s' (Attempt %d/%d)",
                camera_id,
                attempts + 1,
                self.max_reconnect_attempts,
            )
            # Reconnection: Set status to RECONNECTING and restart camera in a separate thread
            # to avoid blocking the health monitor loop.
            camera = self.manager._cameras.get(camera_id)
            if camera is not None:
                camera.status = CameraStatus.RECONNECTING

            threading.Thread(
                target=self._reconnect_camera,
                args=(camera_id,),
                name=f"ReconnectThread_{camera_id}",
                daemon=True,
            ).start()
        else:
            logger.critical(
                "Max reconnection attempts reached for camera '%s'. Marking offline.",
                camera_id,
            )
            self._cleanup_camera_tracking(camera_id)
            # Stop the camera to clean up resources, sets status to DISCONNECTED
            try:
                self.manager.stop_camera(camera_id)
            except Exception as e:
                logger.error("Error stopping camera '%s' after max reconnect failures: %s", camera_id, e)

    def _reconnect_camera(self, camera_id: str) -> None:
        """Perform restart of the camera stream.

        Args:
            camera_id: Unique identifier of the camera to reconnect.
        """
        try:
            self.manager.restart_camera(camera_id)
            logger.info("Successfully reconnected camera '%s'.", camera_id)
        except Exception as e:
            logger.error("Failed reconnection attempt for camera '%s': %s", camera_id, e)

    def _cleanup_camera_tracking(self, camera_id: str) -> None:
        """Clean up caching dictionaries for a specific camera.

        Args:
            camera_id: Unique identifier of the camera.
        """
        self._last_timestamps.pop(camera_id, None)
        self._last_frame_counts.pop(camera_id, None)
        self._last_frames.pop(camera_id, None)
        self._freeze_counts.pop(camera_id, None)
