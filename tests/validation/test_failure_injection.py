"""Failure Injection Validation for AERA.

Simulates subsystem failures (invalid frames, offline streams, detector errors,
evidence failures, and alert notifier failures) to verify graceful error
handling boundaries.
"""

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from src.integration.coordinator import SystemCoordinator
from src.integration.pipeline import EmergencyPipeline
from src.integration.exceptions import PipelineError
from src.detection.exceptions import InferenceError
from src.evidence.exceptions import EvidenceError
from src.alert.exceptions import AlertError


def create_fire_frame() -> np.ndarray:
    """Create a BGR frame with a cluster of fire-colored pixels."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[10:90, 10:90, 2] = 250
    frame[10:90, 10:90, 1] = 10
    frame[10:90, 10:90, 0] = 10
    return frame


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


def test_invalid_camera_failure() -> None:
    """Verify graceful handling of camera failure (None frame)."""
    coordinator = SystemCoordinator()
    coordinator.start()
    pipeline = EmergencyPipeline(coordinator)

    with pytest.raises(PipelineError) as exc:
        pipeline.process_camera_frame("offline_cam", None)  # type: ignore
    assert "Camera failure" in str(exc.value)
    coordinator.stop()


def test_detector_inference_failure() -> None:
    """Verify graceful handling of AI Detector inference crash."""
    coordinator = SystemCoordinator()
    coordinator.start()
    pipeline = EmergencyPipeline(coordinator)

    # Register camera
    coordinator.camera_manager.register_camera("cam_det_fail", "Cam", "dummy")
    coordinator.camera_manager.start_camera("cam_det_fail")

    # Inject detector failure
    with patch.object(
        coordinator.detection_pipeline, "process_frame", side_effect=InferenceError("Inference crash")
    ):
        with pytest.raises(PipelineError) as exc:
            pipeline.process_camera_frame("cam_det_fail", create_fire_frame())
        assert "Pipeline flow failed" in str(exc.value)

    coordinator.stop()


def run_validation() -> Dict[str, Any]:
    """Simulate subsystem failures and verify recovery boundaries.

    Returns:
        Dict: Failure injection validation report.
    """
    warnings: List[str] = []
    tests_summary = {
        "invalid_camera": "FAILED",
        "disconnected_camera": "FAILED",
        "detector_failure": "FAILED",
        "evidence_failure": "FAILED",
        "alert_failure": "FAILED",
    }

    # Mock video capture connection
    with patch("src.camera.stream.cv2.VideoCapture") as mock_video_capture:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        fake_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, fake_frame)
        mock_video_capture.return_value = mock_cap

        coordinator = SystemCoordinator()
        try:
            coordinator.start()
            pipeline = EmergencyPipeline(coordinator)
            frame = create_fire_frame()

            # 1. Test invalid camera (None frame)
            try:
                pipeline.process_camera_frame("cam_invalid", None)  # type: ignore
            except PipelineError:
                tests_summary["invalid_camera"] = "PASSED"
            except Exception as e:
                warnings.append(f"Invalid camera threw unexpected exception: {e}")

            # 2. Test disconnected camera (Offline Camera Status)
            coordinator.camera_manager.register_camera("cam_offline", "Offline Cam", "dummy")
            # camera not started is offline/registered
            try:
                pipeline.process_camera_frame("cam_offline", frame)
            except PipelineError:
                tests_summary["disconnected_camera"] = "PASSED"
            except Exception as e:
                warnings.append(f"Disconnected camera threw unexpected exception: {e}")

            # 3. Test detector failure (InferenceError)
            coordinator.camera_manager.register_camera("cam_det", "Det Cam", "dummy")
            coordinator.camera_manager.start_camera("cam_det")
            with patch.object(
                coordinator.detection_pipeline,
                "process_frame",
                side_effect=InferenceError("Simulated detector error"),
            ):
                try:
                    pipeline.process_camera_frame("cam_det", frame)
                except PipelineError:
                    tests_summary["detector_failure"] = "PASSED"
                except Exception as e:
                    warnings.append(f"Detector failure threw unexpected exception: {e}")

            # 4. Test evidence failure (EvidenceError)
            coordinator.camera_manager.register_camera("cam_ev", "Ev Cam", "dummy")
            coordinator.camera_manager.start_camera("cam_ev")
            with patch.object(
                coordinator.evidence_manager,
                "create_evidence",
                side_effect=EvidenceError("Simulated evidence storage failure"),
            ):
                try:
                    pipeline.process_camera_frame("cam_ev", frame)
                except PipelineError:
                    tests_summary["evidence_failure"] = "PASSED"
                except Exception as e:
                    warnings.append(f"Evidence failure threw unexpected exception: {e}")

            # 5. Test alert failure (AlertError)
            coordinator.camera_manager.register_camera("cam_al", "Al Cam", "dummy")
            coordinator.camera_manager.start_camera("cam_al")
            with patch.object(
                coordinator.alert_manager,
                "trigger_alert",
                side_effect=AlertError("Simulated alert dispatch failure"),
            ):
                try:
                    pipeline.process_camera_frame("cam_al", frame)
                except PipelineError:
                    tests_summary["alert_failure"] = "PASSED"
                except Exception as e:
                    warnings.append(f"Alert failure threw unexpected exception: {e}")

            coordinator.stop()

            # Verify all passed
            all_passed = all(status == "PASSED" for status in tests_summary.values())
            status = "PASSED" if all_passed else "FAILED"

            return {
                "status": status,
                "message": "Subsystem failure injections recovery boundaries verified.",
                "details": tests_summary,
                "warnings": warnings,
            }

        except Exception as e:
            try:
                coordinator.stop()
            except Exception:
                pass
            return {
                "status": "FAILED",
                "message": f"Failure injection setup crash: {e}",
                "details": tests_summary,
                "warnings": [f"Setup crash: {e}"],
            }
