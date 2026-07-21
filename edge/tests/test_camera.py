"""Unit tests for the AERA Camera Management System.

This module contains test cases for exceptions, Camera entity, CameraStream,
CameraManager, and CameraHealthMonitor using unittest.mock to isolate hardware dependencies.
"""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.camera.camera import Camera, CameraStatus
from src.camera.exceptions import (
    CameraAlreadyExistsError,
    CameraConnectionError,
    CameraError,
    CameraInitializationError,
    CameraNotFoundError,
    CameraOfflineError,
)
from src.camera.health import CameraHealthMonitor
from src.camera.manager import CameraManager
from src.camera.stream import CameraStream


# ==============================================================================
# 1. Test Custom Exceptions
# ==============================================================================
def test_exceptions_hierarchy() -> None:
    """Verify exceptions inherit from CameraError and support custom messages."""
    assert issubclass(CameraConnectionError, CameraError)
    assert issubclass(CameraNotFoundError, CameraError)
    assert issubclass(CameraAlreadyExistsError, CameraError)

    exc = CameraConnectionError("Custom connection failed")
    assert str(exc) == "Custom connection failed"
    assert exc.message == "Custom connection failed"


# ==============================================================================
# 2. Test Camera Entity
# ==============================================================================
def test_camera_entity_initialization() -> None:
    """Verify lightweight Camera class initializes with default values."""
    config = {"frame_rate": 30}
    metadata = {"location": "Front Door"}
    camera = Camera(
        camera_id="cam_01",
        name="Front Gate",
        source="rtsp://fake_stream",
        config=config,
        metadata=metadata,
    )

    assert camera.camera_id == "cam_01"
    assert camera.name == "Front Gate"
    assert camera.source == "rtsp://fake_stream"
    assert camera.config == config
    assert camera.metadata == metadata
    assert camera.status == CameraStatus.REGISTERED
    assert "cam_01" in repr(camera)


# ==============================================================================
# 3. Test CameraStream (Mocking OpenCV)
# ==============================================================================
@patch("src.camera.stream.cv2.VideoCapture")
def test_stream_connection_success(mock_video_capture: MagicMock) -> None:
    """Test successful camera connection and configuration application."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_video_capture.return_value = mock_cap

    config = {"resolution": {"width": 1920, "height": 1080}}
    stream = CameraStream(source="0", config=config)
    stream.connect()

    assert stream.is_connected() is True
    mock_cap.set.assert_any_call(3, 1920)  # CAP_PROP_FRAME_WIDTH
    mock_cap.set.assert_any_call(4, 1080)  # CAP_PROP_FRAME_HEIGHT


@patch("src.camera.stream.cv2.VideoCapture")
def test_stream_connection_failure(mock_video_capture: MagicMock) -> None:
    """Verify CameraConnectionError is raised if OpenCV VideoCapture fails to open."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    mock_video_capture.return_value = mock_cap

    stream = CameraStream(source="0")
    with pytest.raises(CameraConnectionError):
        stream.connect()


@patch("src.camera.stream.cv2.VideoCapture")
def test_stream_grabbing_loop(mock_video_capture: MagicMock) -> None:
    """Verify background capture thread reads frames and increments frame counter."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    # Return fake frame
    fake_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)
    mock_video_capture.return_value = mock_cap
    stream = CameraStream(source="0", config={"frame_rate": 100})
    stream.connect()
    stream.start_stream()

    # Allow thread to run briefly
    time.sleep(0.1)

    assert stream.frame_count > 0
    timestamp, frame = stream.read_frame()
    stream.disconnect()

    assert timestamp > 0.0
    assert frame is not None
    assert np.array_equal(frame, fake_frame)


# ==============================================================================
# 4. Test CameraManager (Non-Singleton)
# ==============================================================================
@patch("src.camera.stream.cv2.VideoCapture")
def test_manager_registration_and_removal(mock_video_capture: MagicMock) -> None:
    """Verify registering and removing cameras from manager updates registry."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_video_capture.return_value = mock_cap

    manager = CameraManager()
    assert len(manager.list_cameras()) == 0

    # Register camera
    cam = manager.register_camera(camera_id="cam_01", name="Cam 1", source="0")
    assert len(manager.list_cameras()) == 1
    assert cam.status == CameraStatus.REGISTERED

    # Prevent duplicate ID registration
    with pytest.raises(CameraAlreadyExistsError):
        manager.register_camera(camera_id="cam_01", name="Cam 1 Dup", source="1")

    # Remove camera
    manager.remove_camera(camera_id="cam_01")
    assert len(manager.list_cameras()) == 0

    # Removing non-existent camera raises error
    with pytest.raises(CameraNotFoundError):
        manager.remove_camera("cam_01")


@patch("src.camera.stream.cv2.VideoCapture")
def test_manager_start_stop_flow(mock_video_capture: MagicMock) -> None:
    """Verify starting and stopping camera updates CameraStatus appropriately."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.zeros((5, 5, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)
    mock_video_capture.return_value = mock_cap

    manager = CameraManager()
    manager.register_camera(camera_id="test_cam", name="Test Cam", source="0")

    assert manager.camera_status("test_cam") == CameraStatus.REGISTERED

    # Start camera
    manager.start_camera("test_cam")
    assert manager.camera_status("test_cam") == CameraStatus.STREAMING

    # Allow thread to run briefly to fetch a frame
    time.sleep(0.1)

    # Read frame
    ts, frame = manager.get_frame("test_cam")
    assert ts > 0
    assert frame is not None

    # Stop camera
    manager.stop_camera("test_cam")
    assert manager.camera_status("test_cam") == CameraStatus.DISCONNECTED

    # Attempting to fetch frame from stopped camera raises error
    with pytest.raises(CameraOfflineError):
        manager.get_frame("test_cam")

    manager.shutdown()


# ==============================================================================
# 5. Test CameraHealthMonitor
# ==============================================================================
@patch("src.camera.stream.cv2.VideoCapture")
def test_health_monitor_timeout_and_reconnection(mock_video_capture: MagicMock) -> None:
    """Verify health monitor triggers reconnection if frame timeout is met."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.zeros((5, 5, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)
    mock_video_capture.return_value = mock_cap

    manager = CameraManager()
    manager.register_camera(camera_id="health_cam", name="Health Cam", source="0")
    manager.start_camera("health_cam")

    # Set up health monitor with extremely short timeout
    health_monitor = CameraHealthMonitor(
        manager=manager,
        check_interval=0.1,
        timeout_threshold=0.05,
        max_reconnect_attempts=2,
    )

    # Induce artificial timeout by setting latest_timestamp to a long time ago
    stream = manager._streams["health_cam"]
    with stream._lock:
        stream._latest_timestamp = time.time() - 10.0

    # Start health monitor
    health_monitor.start()
    time.sleep(0.3)
    health_monitor.stop()

    # Reconnection should be triggered and status becomes STREAMING again or keeps trying
    # Since mock always connects successfully, status should recover to STREAMING
    assert manager.camera_status("health_cam") == CameraStatus.STREAMING
    manager.shutdown()


@patch("src.camera.stream.cv2.VideoCapture")
def test_health_monitor_frozen_detection(mock_video_capture: MagicMock) -> None:
    """Verify health monitor detects frozen content and triggers restart."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.zeros((5, 5, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)
    mock_video_capture.return_value = mock_cap

    manager = CameraManager()
    manager.register_camera(camera_id="frozen_cam", name="Frozen Cam", source="0")
    manager.start_camera("frozen_cam")

    # Health monitor with freeze audits
    health_monitor = CameraHealthMonitor(
        manager=manager,
        check_interval=0.05,
        timeout_threshold=5.0,
        max_reconnect_attempts=2,
    )

    # In this case, read_frame() will always return the same timestamp and frame,
    # but we can trick it by manually feeding same frame content with changing timestamps
    stream = manager._streams["frozen_cam"]

    # Mock restart_camera to observe calls
    original_restart = manager.restart_camera
    manager.restart_camera = MagicMock(side_effect=original_restart)

    health_monitor.start()

    # Simulate 6 check ticks where timestamp updates but frame contents stay identical.
    # We update self._last_timestamps so timeout isn't hit, but frame remains identical.
    for i in range(6):
        with stream._lock:
            stream._latest_timestamp = time.time()
            stream.frame_count += 1
        time.sleep(0.06)

    health_monitor.stop()

    # Reconnection (restart) should have been triggered at least once due to frame freeze
    assert manager.restart_camera.call_count >= 1
    manager.shutdown()
