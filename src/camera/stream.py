"""Camera stream management using OpenCV for the AERA Camera Management System.

This module encapsulates all direct OpenCV operations, providing a thread-safe
CameraStream class that reads frames in a background thread to prevent buffer lag
and provides access to only the latest captured frame.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple, Union

import cv2
import numpy as np

from .exceptions import (
    CameraConnectionError,
    CameraInitializationError,
    FrameReadError,
    InvalidCameraSourceError,
)

logger = logging.getLogger(__name__)


class CameraStream:
    """Manages connection and frame acquisition from a single camera source using OpenCV.

    Runs a background thread to continuously pull frames from the source.
    This guarantees that the OpenCV internal buffer is always flushed,
    minimizing latency and ensuring consumers always receive the freshest frame.
    """

    def __init__(
        self,
        source: Union[int, str],
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the CameraStream instance.

        Args:
            source: Integer for USB/webcam index, or string for RTSP URI/video file path.
            config: Optional configuration dictionary containing:
                - 'frame_rate' (int/float): Target FPS to regulate reading.
                - 'resolution' (dict): Optional width and height dictionary.
        """
        self.source = source
        self.config = config if config is not None else {}

        # Parse source if it is a string representing an integer (e.g. "0")
        self._parsed_source = self._parse_source(source)

        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_timestamp: float = 0.0
        self.frame_count: int = 0

        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Consecutive frame read error counter
        self._consecutive_errors: int = 0
        self._max_consecutive_errors: int = 15

    @staticmethod
    def _parse_source(source: Union[int, str]) -> Union[int, str]:
        """Convert source to integer if it is a digit-only string.

        Args:
            source: Raw source identifier.

        Returns:
            Parsed source (integer index or string URI/path).
        """
        if isinstance(source, str) and source.strip().isdigit():
            return int(source.strip())
        return source

    def connect(self) -> None:
        """Establish connection with the camera source.

        Raises:
            CameraConnectionError: If OpenCV fails to open the video source.
            CameraInitializationError: If unexpected errors occur during setup.
        """
        with self._lock:
            if self._cap is not None and self._cap.isOpened():
                logger.warning("CameraStream source %s is already connected.", self.source)
                return

            logger.info("Connecting to camera source: %s", self.source)
            try:
                # Open the stream
                cap = cv2.VideoCapture(self._parsed_source)
                if not cap.isOpened():
                    raise CameraConnectionError(
                        f"OpenCV failed to open camera source: {self.source}"
                    )

                self._cap = cap
                self._apply_configurations()
                self._consecutive_errors = 0
                logger.info("Successfully connected to camera source: %s", self.source)

            except CameraConnectionError:
                raise
            except Exception as e:
                logger.exception("Unexpected error during camera initialization: %s", e)
                raise CameraInitializationError(
                    f"Unexpected initialization error for source {self.source}: {e}"
                ) from e

    def _apply_configurations(self) -> None:
        """Apply configured resolution settings to cv2.VideoCapture object."""
        if not self._cap:
            return

        resolution = self.config.get("resolution")
        if isinstance(resolution, dict):
            width = resolution.get("width")
            height = resolution.get("height")
            if isinstance(width, int) and isinstance(height, int):
                logger.info(
                    "Setting resolution to %dx%d for source %s", width, height, self.source
                )
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def start_stream(self) -> None:
        """Start the background frame capture thread.

        Raises:
            CameraConnectionError: If camera is not connected before starting stream.
        """
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                raise CameraConnectionError(
                    f"Cannot start streaming. Source {self.source} is not connected."
                )

            if self._running:
                logger.warning("Stream for source %s is already running.", self.source)
                return

            self._running = True
            self._thread = threading.Thread(
                target=self._capture_loop,
                name=f"CameraStreamThread_{self.source}",
                daemon=True,
            )
            self._thread.start()
            logger.info("Started background capture thread for source: %s", self.source)

    def _capture_loop(self) -> None:
        """Background thread target to continuously read frames from OpenCV stream."""
        target_fps = self.config.get("frame_rate", 30.0)
        frame_delay = 1.0 / target_fps if (isinstance(target_fps, (int, float)) and target_fps > 0) else 0.0

        logger.debug("Starting stream capture loop for source: %s", self.source)

        while self._running:
            start_time = time.time()

            # Verify capture object exists
            cap_obj = None
            with self._lock:
                cap_obj = self._cap

            if cap_obj is None or not cap_obj.isOpened():
                logger.error("VideoCapture object closed unexpectedly for source: %s", self.source)
                self._running = False
                break

            try:
                ret, frame = cap_obj.read()
                if not ret or frame is None:
                    self._consecutive_errors += 1
                    logger.warning(
                        "Failed to read frame from source %s (Consecutive errors: %d/%d)",
                        self.source,
                        self._consecutive_errors,
                        self._max_consecutive_errors,
                    )

                    if self._consecutive_errors >= self._max_consecutive_errors:
                        logger.error(
                            "Consecutive frame read errors exceeded limit. Stopping stream for source: %s",
                            self.source,
                        )
                        self._running = False
                        break

                    # Sleep briefly before retrying
                    time.sleep(0.01)
                    continue

                # Successful read: update frame and timestamp
                self._consecutive_errors = 0
                with self._lock:
                    self._latest_frame = frame
                    self._latest_timestamp = time.time()
                    self.frame_count += 1

            except Exception as e:
                logger.exception("Error during frame acquisition loop for source %s: %s", self.source, e)
                self._consecutive_errors += 1
                if self._consecutive_errors >= self._max_consecutive_errors:
                    self._running = False
                    break
                time.sleep(0.01)
                continue

            # Regulate frame rate if configured
            if frame_delay > 0.0:
                elapsed = time.time() - start_time
                sleep_time = frame_delay - elapsed
                if sleep_time > 0.0:
                    time.sleep(sleep_time)

        logger.info("Exited stream capture loop for source: %s", self.source)

    def stop_stream(self) -> None:
        """Stop the background capture thread."""
        logger.info("Stopping stream for source: %s", self.source)
        self._running = False
        if self._thread is not None:
            if self._thread != threading.current_thread():
                self._thread.join(timeout=2.0)
            self._thread = None

    def disconnect(self) -> None:
        """Stop stream and release OpenCV capture resources."""
        self.stop_stream()

        with self._lock:
            if self._cap is not None:
                logger.info("Disconnecting and releasing VideoCapture for source: %s", self.source)
                try:
                    self._cap.release()
                except Exception as e:
                    logger.error("Error releasing VideoCapture for source %s: %s", self.source, e)
                self._cap = None

            self._latest_frame = None
            self._latest_timestamp = 0.0
            self.frame_count = 0

    def read_frame(self) -> Tuple[float, Optional[np.ndarray]]:
        """Return the latest successfully read frame and its timestamp.

        Returns:
            A tuple of (timestamp: float, frame: Optional[np.ndarray]).
            Returns (0.0, None) if no frame has been read yet.
        """
        with self._lock:
            if self._latest_frame is None:
                return 0.0, None
            return self._latest_timestamp, self._latest_frame.copy()

    def is_connected(self) -> bool:
        """Check if the stream is currently connected.

        Returns:
            True if VideoCapture is open, False otherwise.
        """
        with self._lock:
            return self._cap is not None and self._cap.isOpened()
