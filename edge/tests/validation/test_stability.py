"""Long-Run Stability Validation for AERA.

Runs the pipeline continuously to trace memory growth, CPU utilization,
crashes, and frame processing continuity over configurable durations.
"""

import time
import gc
from typing import Any, Dict
from unittest.mock import MagicMock, patch
import numpy as np

try:
    import psutil
except ImportError:
    psutil = None

from src.camera.camera import CameraStatus
from src.integration.coordinator import SystemCoordinator
from src.integration.pipeline import EmergencyPipeline


def create_fire_frame() -> np.ndarray:
    """Create a BGR frame with a cluster of fire-colored pixels."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[10:90, 10:90, 2] = 250
    frame[10:90, 10:90, 1] = 10
    frame[10:90, 10:90, 0] = 10
    return frame


_CURRENT_PROCESS = psutil.Process() if psutil is not None else None


def get_process_memory() -> float:
    """Return process resident memory in MB. Returns 0.0 if psutil is unavailable."""
    if _CURRENT_PROCESS is not None:
        try:
            return float(_CURRENT_PROCESS.memory_info().rss) / (1024.0 * 1024.0)
        except Exception:
            return 0.0
    return 0.0


def get_process_cpu() -> float:
    """Return current process CPU utilization percentage. Returns 0.0 if unavailable."""
    if _CURRENT_PROCESS is not None:
        try:
            return float(_CURRENT_PROCESS.cpu_percent(interval=None))
        except Exception:
            return 0.0
    return 0.0


def test_stability_run() -> None:
    """Verify that a brief continuous run executes without leaks or crashes."""
    res = run_validation(duration_seconds=1.0)
    assert res["status"] == "PASSED"
    assert res["crashes"] == 0
    assert res["processed_frames"] > 0


def run_validation(duration_seconds: float = 3.0) -> Dict[str, Any]:
    """Run continuous frames pipeline verification measuring memory, CPU, and crashes.

    Args:
        duration_seconds: Duration to run stability loop.

    Returns:
        Dict: Stability report.
    """
    warnings = []
    if psutil is None:
        warnings.append("psutil library not found. Memory and CPU profiling is disabled.")

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
            camera_id = "cam_stability"
            coordinator.camera_manager.register_camera(
                camera_id=camera_id,
                name="Stability Test Camera",
                source="dummy_stability",
            )
            coordinator.camera_manager.start_camera(camera_id)

            pipeline = EmergencyPipeline(coordinator)
            frame = create_fire_frame()

            # Warm-up run to load modules, libraries, dynamic dependencies and compiler structures
            for _ in range(5):
                try:
                    pipeline.process_camera_frame(camera_id, frame)
                except Exception:
                    pass
            gc.collect()
            time.sleep(0.2)

            start_mem = get_process_memory()
            cpu_usages = []
            processed_frames = 0
            crashes = 0

            start_time = time.time()
            end_time = start_time + duration_seconds

            # Continuous feed loop
            while time.time() < end_time:
                try:
                    # Process frame
                    pipeline.process_camera_frame(camera_id, frame)
                    processed_frames += 1
                except Exception as e:
                    crashes += 1
                    warnings.append(f"Pipeline crashed on frame {processed_frames}: {e}")

                cpu_usages.append(get_process_cpu())
                # Sleep briefly to pace frame feed (e.g. 30 FPS target)
                time.sleep(0.033)

            coordinator.stop()
            gc.collect()
            time.sleep(0.2)
            end_mem = get_process_memory()

            mem_growth = max(0.0, end_mem - start_mem)
            avg_cpu = sum(cpu_usages) / len(cpu_usages) if cpu_usages else 0.0

            # Generate status
            status = "PASSED" if crashes == 0 else "FAILED"
            if mem_growth > 100.0:  # Warning if memory grew more than 100MB in brief run
                status = "FAILED"
                warnings.append(f"Significant memory growth detected: {mem_growth:.2f} MB")

            return {
                "status": status,
                "message": f"Stability loop ran for {duration_seconds}s.",
                "processed_frames": processed_frames,
                "crashes": crashes,
                "start_memory_mb": start_mem,
                "end_memory_mb": end_mem,
                "memory_growth_mb": mem_growth,
                "avg_cpu_percent": avg_cpu,
                "warnings": warnings,
            }

        except Exception as e:
            try:
                coordinator.stop()
            except Exception:
                pass
            return {
                "status": "FAILED",
                "message": f"Stability loop setup failure: {e}",
                "processed_frames": 0,
                "crashes": 1,
                "start_memory_mb": 0.0,
                "end_memory_mb": 0.0,
                "memory_growth_mb": 0.0,
                "avg_cpu_percent": 0.0,
                "warnings": [f"Setup crash: {e}"],
            }
