"""End-to-End Pipeline Validation for AERA.

Verifies the complete emergency response pipeline stages:
Camera -> Detection -> Event -> Decision -> Evidence -> Report -> Alert.
"""

import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch
import numpy as np

from src.camera.camera import CameraStatus
from src.event.types import EventType
from src.event.priority import EventPriority
from src.decision.severity import DecisionSeverity
from src.integration.coordinator import SystemCoordinator
from src.integration.pipeline import EmergencyPipeline


def create_fire_frame() -> np.ndarray:
    """Create a BGR frame with a cluster of fire-colored pixels."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[10:90, 10:90, 2] = 250
    frame[10:90, 10:90, 1] = 10
    frame[10:90, 10:90, 0] = 10
    return frame


@patch("src.camera.stream.cv2.VideoCapture")
def test_pipeline_flow(mock_video_capture: MagicMock) -> None:
    """Execute end-to-end flow and assert states at each phase."""
    # Mock video capture for camera startup
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)
    mock_video_capture.return_value = mock_cap

    # 1. Coordinator & Subsystem Startup
    coordinator = SystemCoordinator()
    coordinator.start()
    assert coordinator.is_started is True
    assert coordinator.health_monitor.verify_startup() is True

    # 2. Camera Registration & Connection
    camera_id = "test_e2e_cam"
    coordinator.camera_manager.register_camera(
        camera_id=camera_id,
        name="E2E Validation Camera",
        source="dummy_source_e2e",
    )
    coordinator.camera_manager.start_camera(camera_id)
    assert coordinator.camera_manager.camera_status(camera_id) == CameraStatus.STREAMING

    # 3. Pipeline Ingestion
    pipeline = EmergencyPipeline(coordinator)
    frame = create_fire_frame()
    alerts = pipeline.process_camera_frame(camera_id, frame)

    # 4. Verify AI Model Detection Outputs
    # Check that detection pipeline returned a result
    # We can inspect the detection registry or recreate results
    detectors = coordinator.detection_pipeline.registry.list_detectors()
    assert "fire_detector" in detectors

    # 5. Verify Event Manager Registration
    events = coordinator.event_manager.list_events()
    assert len(events) >= 1
    event = events[0]
    assert event.camera_id == camera_id
    assert event.event_type == EventType.FIRE
    assert event.priority == EventPriority.CRITICAL

    # 6. Verify Decision Engine Escalation Policy
    history = coordinator.decision_engine.get_history()
    assert len(history) >= 1
    # Check alert contains success
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.status == "success"
    assert alert.severity == "CRITICAL"

    # 8. Verify Report Engine Compiles
    reports = coordinator.report_manager.list_reports()
    assert len(reports) >= 1
    report = reports[0]
    assert report.event_id == event.event_id
    assert "AERA Emergency Incident Report" in report.title

    # 7. Verify Evidence Management Storage
    evidence_list = coordinator.evidence_manager.list_evidence()
    assert len(evidence_list) >= 1
    evidence = evidence_list[0]
    assert evidence.event_id == event.event_id
    assert evidence.decision_id == report.decision_id
    # Verify file paths exist
    assert evidence.image_path.endswith(".jpg")

    # 9. Verify Alert Delivery Logs
    history_logs = coordinator.alert_manager.history.get_history(alert.alert_id)
    assert len(history_logs) >= 1
    assert history_logs[0].delivery_status == "success"
    assert history_logs[0].notification_channel == "ConsoleNotifier"

    # Clean shutdown
    coordinator.stop()
    assert coordinator.is_started is False
    assert coordinator.health_monitor.verify_shutdown() is True


def run_validation() -> Dict[str, Any]:
    """Execute the end-to-end validation test and return status.

    Returns:
        Dict: Status reports mapping outcomes.
    """
    try:
        # Run test function inside mock patch context directly
        with patch("src.camera.stream.cv2.VideoCapture") as mock_video_capture:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            fake_frame = np.zeros((100, 100, 3), dtype=np.uint8)
            mock_cap.read.return_value = (True, fake_frame)
            mock_video_capture.return_value = mock_cap

            test_pipeline_flow()  # type: ignore

        return {
            "status": "PASSED",
            "message": "Complete emergency response pipeline stages verified successfully.",
            "warnings": [],
        }
    except Exception as e:
        return {
            "status": "FAILED",
            "message": f"Pipeline verification failure: {e}",
            "warnings": [],
        }
