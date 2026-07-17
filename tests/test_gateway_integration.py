"""Integration Tests for AERA BackendGateway API Completion.

Validates that every API method required by the dashboard and specifications exists,
delegates tasks to the correct underlying managers, and handles errors and empty states gracefully.
"""

import pytest
import time
import pandas as pd
from unittest.mock import MagicMock, patch
import numpy as np

from src.dashboard.services.backend import BackendGateway
from src.camera.camera import CameraStatus
from src.event.types import EventType
from src.event.priority import EventPriority
from src.event.status import EventStatus
from src.evidence.evidence import Evidence
from src.report.report import Report
from src.alert.alert import Alert


@pytest.fixture(autouse=True)
def mock_opencv_video_capture():
    """Mock OpenCV's VideoCapture so that all camera streams succeed during testing."""
    with patch("src.camera.stream.cv2.VideoCapture") as mock_cap_class:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        fake_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, fake_frame)
        mock_cap_class.return_value = mock_cap
        yield


def test_missing_methods_exist() -> None:
    """Verify that all newly introduced APIs exist on BackendGateway."""
    gateway = BackendGateway()
    try:
        # Assert methods exist
        assert hasattr(gateway, "get_cameras")
        assert hasattr(gateway, "restart_camera")
        assert hasattr(gateway, "update_incident")
        assert hasattr(gateway, "close_incident")
        assert hasattr(gateway, "delete_incident")
        assert hasattr(gateway, "get_evidence")
        assert hasattr(gateway, "get_evidence_by_event")
        assert hasattr(gateway, "open_evidence")
        assert hasattr(gateway, "export_evidence")
        assert hasattr(gateway, "create_report_for_event")
        assert hasattr(gateway, "export_report")
        assert hasattr(gateway, "retry_alert")
        assert hasattr(gateway, "get_incident_trends")
        assert hasattr(gateway, "get_incident_distribution")
        assert hasattr(gateway, "get_alert_statistics")
        assert hasattr(gateway, "get_camera_uptime_stats")
        assert hasattr(gateway, "get_camera_statistics")
        assert hasattr(gateway, "get_detection_statistics")
        assert hasattr(gateway, "get_pipeline_metrics")
        assert hasattr(gateway, "get_latency_statistics")
        assert hasattr(gateway, "simulate_frame_injection")
        assert hasattr(gateway, "reload_models")
        assert hasattr(gateway, "reset_pipeline")
        assert hasattr(gateway, "update_threshold")
        assert hasattr(gateway, "export_configuration")
    finally:
        gateway.shutdown()


def test_empty_states_and_types() -> None:
    """Verify that empty states return correct data types and do not raise exceptions."""
    gateway = BackendGateway()
    try:
        # Clear any registered state first
        gateway.coordinator.event_manager.clear_events()
        gateway.coordinator.evidence_manager.clear()
        gateway.coordinator.report_manager.clear()
        gateway.coordinator.alert_manager.clear()

        # Check types on empty state
        assert isinstance(gateway.get_cameras(), list)
        assert isinstance(gateway.get_evidence(), list)
        assert isinstance(gateway.get_reports(), list)
        assert isinstance(gateway.get_alerts(), list)

        # Analytics Pandas DataFrames
        assert isinstance(gateway.get_incident_trends(), pd.DataFrame)
        assert isinstance(gateway.get_incident_distribution(), pd.DataFrame)
        assert isinstance(gateway.get_alert_statistics(), pd.DataFrame)
        assert isinstance(gateway.get_camera_uptime_stats(), pd.DataFrame)

        # Dictionary structures
        assert isinstance(gateway.get_camera_statistics(), dict)
        assert isinstance(gateway.get_detection_statistics(), dict)
        assert isinstance(gateway.get_pipeline_metrics(), dict)
        assert isinstance(gateway.get_latency_statistics(), dict)
        assert isinstance(gateway.export_configuration(), dict)

        # NoneType returns for single elements when missing
        assert gateway.get_report("missing_id") is None
        assert gateway.open_evidence("missing_id") is None
        assert gateway.get_evidence_by_event("missing_id") is None
    finally:
        gateway.shutdown()


def test_camera_and_incident_delegation() -> None:
    """Verify that camera and incident manipulation requests delegate correctly to subsystem managers."""
    gateway = BackendGateway()
    try:
        # 1. Test get_cameras
        cameras = gateway.get_cameras()
        assert len(cameras) >= 3
        camera_id = cameras[0].camera_id

        # 2. Test restart_camera
        success, msg = gateway.restart_camera(camera_id)
        assert success is True

        # 3. Register and create event incident
        event = gateway.coordinator.event_manager.create_event(
            event_type=EventType.SMOKE,
            camera_id=camera_id,
            description="Integration smoke test",
            confidence=0.85,
            priority=EventPriority.HIGH
        )

        # 4. Test update_incident
        success, msg = gateway.update_incident(event.event_id, description="Updated smoke test description")
        assert success is True
        assert gateway.coordinator.event_manager.get_event(event.event_id).description == "Updated smoke test description"

        # 5. Test close_incident
        success, msg = gateway.close_incident(event.event_id)
        assert success is True
        assert gateway.coordinator.event_manager.get_event(event.event_id).status == EventStatus.RESOLVED

        # 6. Test delete_incident
        success, msg = gateway.delete_incident(event.event_id)
        assert success is True
        with pytest.raises(Exception):
            gateway.coordinator.event_manager.get_event(event.event_id)
    finally:
        gateway.shutdown()


def test_evidence_and_report_compilation() -> None:
    """Verify manual compilation of reports and evidence querying."""
    gateway = BackendGateway()
    try:
        camera_id = "webcam_0"
        event = gateway.coordinator.event_manager.create_event(
            event_type=EventType.FIRE,
            camera_id=camera_id,
            description="Verification fire test",
            confidence=0.99,
            priority=EventPriority.CRITICAL
        )

        # Manually compile report
        success, report = gateway.create_report_for_event(event.event_id)
        assert success is True
        assert isinstance(report, Report)
        assert report.event_id == event.event_id

        # Assert report shows up in listings
        reports = gateway.get_reports()
        assert any(r.report_id == report.report_id for r in reports)

        # Assert evidence was created and gets queried
        evidence = gateway.get_evidence_by_event(event.event_id)
        assert evidence is not None
        assert evidence.event_id == event.event_id

        ev_list = gateway.get_evidence()
        assert any(e.evidence_id == evidence.evidence_id for e in ev_list)

        # Test export methods
        success, ev_export = gateway.export_evidence(evidence.evidence_id)
        assert success is True
        assert evidence.evidence_id in ev_export

        success, rep_export = gateway.export_report(report.report_id)
        assert success is True
        assert report.report_id in rep_export
    finally:
        gateway.shutdown()


def test_system_settings_endpoints() -> None:
    """Verify reload, reset, update_threshold, and configuration export methods."""
    gateway = BackendGateway()
    try:
        # Threshold update
        success, msg = gateway.update_threshold("fire_detector", 0.65)
        assert success is True
        assert gateway.coordinator.detection_pipeline.registry.get_detector("fire_detector").confidence_threshold == 0.65

        # Reload models
        success, msg = gateway.reload_models()
        assert success is True

        # Export config
        config = gateway.export_configuration()
        assert "detector_fire_detector" in config
        assert config["detector_fire_detector"]["confidence_threshold"] == 0.65

        # Reset pipeline
        success, msg = gateway.reset_pipeline()
        assert success is True
    finally:
        gateway.shutdown()
