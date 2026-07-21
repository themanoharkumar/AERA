"""Multi-Camera Pipeline Validation for AERA.

Verifies independent frame processing, thread safety, and camera ID mapping
across multiple concurrent streams.
"""

import concurrent.futures
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import numpy as np

from src.alert.alert import Alert
from src.event.types import EventType
from src.integration.coordinator import SystemCoordinator
from src.integration.pipeline import EmergencyPipeline


def create_fire_frame() -> np.ndarray:
    """Create a BGR frame with a cluster of fire-colored pixels."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[10:90, 10:90, 2] = 250
    frame[10:90, 10:90, 1] = 10
    frame[10:90, 10:90, 0] = 10
    return frame


def create_smoke_frame() -> np.ndarray:
    """Create a BGR frame with a cluster of smoke grayish pixels."""
    return np.full((100, 100, 3), 150, dtype=np.uint8)


def create_normal_frame() -> np.ndarray:
    """Create a black empty BGR frame."""
    return np.zeros((100, 100, 3), dtype=np.uint8)


def test_multicamera_execution() -> None:
    """Verify concurrent processing from independent camera streams."""
    res = run_validation()
    assert res["status"] == "PASSED"
    assert res["processed_cameras"] == 3


def run_validation() -> Dict[str, Any]:
    """Execute multi-camera verification checking independent processing and thread safety.

    Returns:
        Dict: Multi-camera verification report.
    """
    warnings: List[str] = []

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

            # 1. Register 3 independent cameras representing webcam, local files, etc.
            cameras_config = [
                {"id": "webcam_0", "name": "Webcam Feed", "frame_fn": create_fire_frame},
                {"id": "local_video_1", "name": "Corridor File", "frame_fn": create_smoke_frame},
                {"id": "local_video_2", "name": "Lobby File", "frame_fn": create_normal_frame},
            ]

            for cfg in cameras_config:
                coordinator.camera_manager.register_camera(
                    camera_id=cfg["id"],
                    name=cfg["name"],
                    source="dummy_source",
                )
                coordinator.camera_manager.start_camera(cfg["id"])

            pipeline = EmergencyPipeline(coordinator)

            # 2. Define concurrent execution worker
            def worker(camera_id: str, frame_fn: Any) -> List[Alert]:
                frame = frame_fn()
                # Run the pipeline thread-safely
                return pipeline.process_camera_frame(camera_id, frame)

            results_map: Dict[str, List[Alert]] = {}

            # 3. Trigger concurrent execution using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures_to_cam = {
                    executor.submit(worker, cfg["id"], cfg["frame_fn"]): cfg["id"]
                    for cfg in cameras_config
                }
                for future in concurrent.futures.as_completed(futures_to_cam):
                    cam_id = futures_to_cam[future]
                    try:
                        results_map[cam_id] = future.result()
                    except Exception as e:
                        warnings.append(f"Camera stream '{cam_id}' worker failed: {e}")
                        results_map[cam_id] = []

            # 4. Verify independent processing results
            # webcam_0 (fire) -> alert created, CRITICAL severity
            webcam_alerts = results_map.get("webcam_0", [])
            assert len(webcam_alerts) == 1
            assert webcam_alerts[0].severity == "CRITICAL"

            # local_video_1 (smoke) -> alert created, HIGH severity
            smoke_alerts = results_map.get("local_video_1", [])
            assert len(smoke_alerts) == 1
            assert smoke_alerts[0].severity == "HIGH"

            # local_video_2 (normal) -> no alerts
            normal_alerts = results_map.get("local_video_2", [])
            assert len(normal_alerts) == 0

            # 5. Verify correct camera IDs in Evidence
            evidence_records = coordinator.evidence_manager.list_evidence()
            assert len(evidence_records) == 2  # fire + smoke evidence

            found_cam_ids = {rec.metadata["camera_id"] for rec in evidence_records}
            assert "webcam_0" in found_cam_ids
            assert "local_video_1" in found_cam_ids
            assert "local_video_2" not in found_cam_ids

            coordinator.stop()

            status = "PASSED" if not warnings else "FAILED"
            return {
                "status": status,
                "message": "Independent concurrent streams processed successfully.",
                "processed_cameras": len(cameras_config),
                "warnings": warnings,
            }

        except Exception as e:
            try:
                coordinator.stop()
            except Exception:
                pass
            return {
                "status": "FAILED",
                "message": f"Multi-camera validation setup failure: {e}",
                "processed_cameras": 0,
                "warnings": [f"Setup crash: {e}"],
            }
