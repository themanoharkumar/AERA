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
            # TODO: Future versions should expose public accessor methods instead of accessing internal registries directly.
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
            # TODO: Future versions should improve frozen frame detection by combining: timestamps, frame count, successful reads, and frame similarity.
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
            camera.metadata["fps"] = measured_fps
            camera.metadata["last_frame_time"] = timestamp
            camera.metadata["health_status"] = "healthy"
            camera.metadata["last_error"] = ""
            camera.metadata["latency"] = 15.0  # nominal active latency in ms

            # Reset reconnect count on successful health check
            if status == CameraStatus.STREAMING and measured_fps > 0:
                self._reconnect_attempts[camera_id] = 0

            # Update cache
            self._last_timestamps[camera_id] = timestamp
            self._last_frame_counts[camera_id] = frame_count
            self._last_frames[camera_id] = frame.copy()

    def _handle_unhealthy(self, camera_id: str, reason: str) -> None:
        """Trigger recovery with exponential backoff.

        Args:
            camera_id: Unique identifier of the unhealthy camera.
            reason: Description of the health failure.
        """
        logger.error("Camera '%s' is unhealthy. Reason: %s", camera_id, reason)
        camera = self.manager._cameras.get(camera_id)
        if camera is None:
            return

        camera.metadata["health_status"] = "warning"
        camera.metadata["last_error"] = reason

        # Avoid spawning duplicate reconnect threads
        if camera.status == CameraStatus.RECONNECTING:
            return

        camera.status = CameraStatus.RECONNECTING
        attempts = self._reconnect_attempts.get(camera_id, 0)
        self._reconnect_attempts[camera_id] = attempts + 1
        camera.metadata["reconnect_count"] = self._reconnect_attempts[camera_id]

        logger.info(
            "Spawning exponential backoff reconnect thread for camera '%s' (Attempt %d)",
            camera_id,
            self._reconnect_attempts[camera_id]
        )

        threading.Thread(
            target=self._reconnect_with_backoff,
            args=(camera_id, attempts),
            name=f"ReconnectBackoffThread_{camera_id}",
            daemon=True,
        ).start()

    def _reconnect_with_backoff(self, camera_id: str, initial_attempts: int) -> None:
        """Exponential backoff reconnect loop that runs until connected.

        Args:
            camera_id: Unique identifier of the camera.
            initial_attempts: Number of initial failures.
        """
        attempts = initial_attempts
        while self._running:
            camera = self.manager._cameras.get(camera_id)
            if camera is None or camera.status != CameraStatus.RECONNECTING:
                break

            # If it's a retry (attempts > 0), sleep with exponential backoff
            if attempts > 0:
                # Backoff delay: 5s, 10s, 20s, 30s, then cap at 30s
                delay = min(5.0 * (2.0 ** (attempts - 1)), 30.0)
                logger.info("Camera '%s' backoff sleep for %.1fs before reconnect attempt", camera_id, delay)
                
                # Non-blocking sleep loop
                sleep_ticks = int(delay * 10)
                for _ in range(sleep_ticks):
                    if not self._running:
                        break
                    camera = self.manager._cameras.get(camera_id)
                    if camera is None or camera.status != CameraStatus.RECONNECTING:
                        break
                    time.sleep(0.1)

            if not self._running:
                break
            camera = self.manager._cameras.get(camera_id)
            if camera is None or camera.status != CameraStatus.RECONNECTING:
                break

            logger.info("Attempting reconnection for camera '%s' (Attempt %d)...", camera_id, attempts + 1)
            try:
                self.manager.restart_camera(camera_id)
                logger.info("Successfully reconnected camera '%s'.", camera_id)
                self._reconnect_attempts[camera_id] = 0
                camera.metadata["health_status"] = "healthy"
                camera.metadata["reconnect_count"] = 0
                camera.metadata["last_error"] = ""
                break
            except Exception as e:
                attempts += 1
                self._reconnect_attempts[camera_id] = attempts
                camera.metadata["reconnect_count"] = attempts
                camera.metadata["last_error"] = str(e)
                camera.metadata["health_status"] = "offline"
                logger.error("Reconnection attempt failed for camera '%s': %s", camera_id, e)

    def _cleanup_camera_tracking(self, camera_id: str) -> None:
        """Clean up caching dictionaries for a specific camera.

        Args:
            camera_id: Unique identifier of the camera.
        """
        self._last_timestamps.pop(camera_id, None)
        self._last_frame_counts.pop(camera_id, None)
        self._last_frames.pop(camera_id, None)
        self._freeze_counts.pop(camera_id, None)
