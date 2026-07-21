"""Shared fixtures for AERA validation tests."""

from typing import Generator
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from src.integration.coordinator import SystemCoordinator
from src.integration.pipeline import EmergencyPipeline


@pytest.fixture(autouse=True)
def mock_cv2_capture() -> Generator[MagicMock, None, None]:
    """Fixture to mock cv2.VideoCapture so dummy sources connect successfully."""
    with patch("src.camera.stream.cv2.VideoCapture") as mock_video_capture:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        fake_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, fake_frame)
        mock_video_capture.return_value = mock_cap
        yield mock_video_capture


@pytest.fixture
def coordinator() -> Generator[SystemCoordinator, None, None]:
    """Provide a started SystemCoordinator instance."""
    coord = SystemCoordinator()
    coord.start()
    yield coord
    coord.stop()


@pytest.fixture
def pipeline(coordinator: SystemCoordinator) -> EmergencyPipeline:
    """Provide an EmergencyPipeline instance."""
    return EmergencyPipeline(coordinator)


@pytest.fixture
def registered_camera(coordinator: SystemCoordinator) -> str:
    """Register and start a camera, returning its camera_id."""
    camera_id = "test_fixture_cam"
    coordinator.camera_manager.register_camera(
        camera_id=camera_id,
        name="Fixture Camera",
        source="dummy_source",
    )
    coordinator.camera_manager.start_camera(camera_id)
    return camera_id


@pytest.fixture
def fire_frame() -> np.ndarray:
    """Provide a BGR frame with a cluster of fire-colored pixels."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[10:90, 10:90, 2] = 250
    frame[10:90, 10:90, 1] = 10
    frame[10:90, 10:90, 0] = 10
    return frame
