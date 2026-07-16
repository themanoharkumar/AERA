"""Integration tests for the AERA System Integration layer.

Verifies end-to-end processing pipelines, startup and shutdown lifecycles,
error boundaries on camera disconnection, and multi-threaded streams concurrency.
"""

import time
import concurrent.futures
from typing import Any, List
import numpy as np
import pytest

from src.integration import (
    SystemCoordinator,
    EmergencyPipeline,
    PipelineError,
    ValidationError,
)
from src.camera.camera import CameraStatus
from src.camera.exceptions import CameraOfflineError
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def mock_cv2_capture() -> Any:
    """Fixture to mock cv2.VideoCapture so dummy sources connect successfully."""
    with patch("src.camera.stream.cv2.VideoCapture") as mock_video_capture:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        fake_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, fake_frame)
        mock_video_capture.return_value = mock_cap
        yield mock_video_capture


# ==============================================================================
# Helper to construct test frames
# ==============================================================================
def create_fire_frame() -> np.ndarray:
    """Create a BGR frame with a cluster of fire-colored pixels."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Red is channel 2. High red, low green and blue
    frame[10:90, 10:90, 2] = 250
    frame[10:90, 10:90, 1] = 10
    frame[10:90, 10:90, 0] = 10
    return frame


def create_smoke_frame() -> np.ndarray:
    """Create a BGR frame with a cluster of smoke-colored (gray) pixels."""
    frame = np.full((100, 100, 3), 150, dtype=np.uint8)
    return frame


# ==============================================================================
# Integration Scenarios
# ==============================================================================
def test_scenario_1_fire_detection_e2e() -> None:
    """Scenario 1: Fire detection triggers the entire pipeline successfully."""
    # 1. Initialize and start coordinator
    coordinator = SystemCoordinator()
    coordinator.start()

    # 2. Register and start camera
    cam = coordinator.camera_manager.register_camera(
        camera_id="cam_fire",
        name="Fire Safety Camera",
        source="dummy_source",
    )

    # Transition status to STREAMING so pipeline allows frames
    coordinator.camera_manager.start_camera("cam_fire")

    # 3. Create pipeline
    pipeline = EmergencyPipeline(coordinator)

    # 4. Generate frame and process
    frame = create_fire_frame()
    alerts = pipeline.process_camera_frame("cam_fire", frame)

    # 5. Verify results
    assert len(alerts) >= 1
    assert alerts[0].status == "success"
    assert alerts[0].severity in ("HIGH", "CRITICAL")
    assert alerts[0].report_id is not None

    # Check alert history is recorded
    history_logs = coordinator.alert_manager.history.get_history(alerts[0].alert_id)
    assert len(history_logs) >= 1
    assert history_logs[0].delivery_status == "success"

    # 6. Stop coordinator cleanly
    coordinator.stop()


def test_scenario_2_smoke_detection_e2e() -> None:
    """Scenario 2: Smoke detection triggers the entire pipeline successfully."""
    coordinator = SystemCoordinator()
    coordinator.start()

    coordinator.camera_manager.register_camera(
        camera_id="cam_smoke",
        name="Smoke Safety Camera",
        source="dummy_source",
    )
    coordinator.camera_manager.start_camera("cam_smoke")

    pipeline = EmergencyPipeline(coordinator)

    frame = create_smoke_frame()
    alerts = pipeline.process_camera_frame("cam_smoke", frame)

    assert len(alerts) >= 1
    assert alerts[0].status == "success"
    assert alerts[0].report_id is not None

    coordinator.stop()


def test_scenario_3_camera_failure() -> None:
    """Scenario 3: Camera failure is handled gracefully with PipelineError."""
    coordinator = SystemCoordinator()
    coordinator.start()

    pipeline = EmergencyPipeline(coordinator)

    # Try processing invalid frame
    with pytest.raises(PipelineError) as exc:
        pipeline.process_camera_frame("cam_failed", None)  # type: ignore
    assert "Camera failure" in str(exc.value)

    coordinator.stop()


def test_scenario_4_concurrent_cameras() -> None:
    """Scenario 4: Concurrent cameras execute pipelines concurrently and thread-safely."""
    coordinator = SystemCoordinator()
    coordinator.start()

    # Register and start two cameras
    coordinator.camera_manager.register_camera("cam_c1", "Cam 1", "dummy_source")
    coordinator.camera_manager.register_camera("cam_c2", "Cam 2", "dummy_source")

    coordinator.camera_manager.start_camera("cam_c1")
    coordinator.camera_manager.start_camera("cam_c2")

    pipeline = EmergencyPipeline(coordinator)

    def worker(camera_id: str, frame: np.ndarray) -> List[Any]:
        return pipeline.process_camera_frame(camera_id, frame)

    frame_fire = create_fire_frame()
    frame_smoke = create_smoke_frame()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker, "cam_c1", frame_fire)
        f2 = executor.submit(worker, "cam_c2", frame_smoke)
        concurrent.futures.wait([f1, f2])

        alerts_c1 = f1.result()
        alerts_c2 = f2.result()

    # Verify both pipelines processed successfully
    assert len(alerts_c1) >= 1
    assert len(alerts_c2) >= 1
    assert alerts_c1[0].status == "success"
    assert alerts_c2[0].status == "success"

    # Wiping state
    coordinator.stop()
