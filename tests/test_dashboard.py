"""Functionality Verification and Integration Tests for AERA Dashboard Service Layer.

Verifies that BackendGateway connects, registers, queries, and mutates coordinator
subsystems safely and handles failures gracefully.
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from src.dashboard.services.backend import BackendGateway
from src.camera.camera import CameraStatus
from src.event.types import EventType
from src.event.priority import EventPriority
from src.event.status import EventStatus
import numpy as np

@pytest.fixture(autouse=True)
def mock_video_capture():
    """Mock OpenCV's VideoCapture so that all camera streams succeed during testing."""
    with patch("src.camera.stream.cv2.VideoCapture") as mock_cap_class:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        fake_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, fake_frame)
        mock_cap_class.return_value = mock_cap
        yield



def test_gateway_lifecycle() -> None:
    """Verify that the BackendGateway initializes, registers default cameras, and shuts down."""
    # Instantiating the gateway initializes the SystemCoordinator and registers defaults
    gateway = BackendGateway()
    try:
        # Check default cameras registered
        cameras = gateway.list_cameras()
        assert len(cameras) == 3
        camera_ids = [c.camera_id for c in cameras]
        assert "webcam_0" in camera_ids
        assert "local_video_1" in camera_ids
        assert "local_video_2" in camera_ids

        # Check health and metrics
        health = gateway.get_system_health()
        assert "overall_healthy" in health
        
        perf = gateway.get_performance_metrics()
        assert "fps" in perf
        assert perf["latency_total"] > 0
    finally:
        gateway.shutdown()


def test_gateway_camera_mutations() -> None:
    """Verify that the gateway starts, stops, registers, and removes cameras correctly."""
    gateway = BackendGateway()
    try:
        # Try to register a new camera
        success, msg = gateway.register_camera(
            camera_id="test_cam_99",
            name="Testing Feed",
            source="dummy_source_99"
        )
        assert success is True
        assert "registered" in msg

        # Try to start it
        success, msg = gateway.start_camera("test_cam_99")
        assert success is True

        # Try to stop it
        success, msg = gateway.stop_camera("test_cam_99")
        assert success is True

        # Try to remove it
        success, msg = gateway.remove_camera("test_cam_99")
        assert success is True
        assert gateway.get_camera("test_cam_99") is None
    finally:
        gateway.shutdown()


def test_gateway_incident_queries_and_simulation() -> None:
    """Verify incident filtering, status updates, and simulation triggers."""
    gateway = BackendGateway()
    try:
        # Trigger an incident simulation on one of the registered cameras
        # We start the camera webcam_0 first (even if offline, dummy is fine)
        gateway.start_camera("webcam_0")
        
        # Trigger simulation
        success, msg = gateway.trigger_incident_simulation("webcam_0", "FIRE")
        assert success is True

        # Check if the incident registered in the EventManager
        incidents = gateway.get_incidents()
        assert len(incidents) > 0
        
        event = incidents[0]
        assert event.camera_id == "webcam_0"
        assert event.event_type == EventType.FIRE

        # Try updating status
        success, msg = gateway.update_incident_status(event.event_id, "PROCESSING")
        assert success is True
        
        updated_event = gateway.get_incident(event.event_id)
        assert updated_event is not None
        assert updated_event.status == EventStatus.PROCESSING

        # Check evidence and reports generated for simulated incident
        evidence = gateway.get_evidence_for_event(event.event_id)
        assert evidence is not None
        assert evidence.event_id == event.event_id

        reports = gateway.get_reports()
        assert len(reports) > 0
        matching_rep = [r for r in reports if r.event_id == event.event_id]
        assert len(matching_rep) > 0
    finally:
        gateway.shutdown()
