"""Thread Safety & Stress Validation for AERA.

Stresses the pipeline with multiple concurrent threads delivering frames
simultaneously, verifying that AERA remains free from deadlocks, race conditions,
and crashes under concurrent load.
"""

import concurrent.futures
import queue
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import numpy as np

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


def create_smoke_frame() -> np.ndarray:
    """Create a BGR frame with a cluster of smoke grayish pixels."""
    return np.full((100, 100, 3), 150, dtype=np.uint8)


def create_normal_frame() -> np.ndarray:
    """Create a black empty BGR frame."""
    return np.zeros((100, 100, 3), dtype=np.uint8)


def test_concurrency_stress() -> None:
    """Verify that concurrent worker stress runs cleanly without race conditions or deadlocks."""
    res = run_validation(num_threads=4, iterations_per_thread=10)
    assert res["status"] == "PASSED"
    assert res["crashes"] == 0


def run_validation(num_threads: int = 5, iterations_per_thread: int = 20) -> Dict[str, Any]:
    """Stress-test concurrent pipeline flows, auditing deadlocks and race conditions.

    Args:
        num_threads: Number of concurrent threads to spawn.
        iterations_per_thread: Number of frames per thread.

    Returns:
        Dict: Threading validation report.
    """
    warnings: List[str] = []
    error_queue: queue.Queue = queue.Queue()

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

            # 1. Register a camera for each thread
            for i in range(num_threads):
                coordinator.camera_manager.register_camera(
                    camera_id=f"cam_thread_{i}",
                    name=f"Stress Cam {i}",
                    source="dummy_source",
                )
                coordinator.camera_manager.start_camera(f"cam_thread_{i}")

            pipeline = EmergencyPipeline(coordinator)

            # 2. Define worker task
            def worker(thread_idx: int) -> int:
                cam_id = f"cam_thread_{thread_idx}"
                local_processed = 0

                # Alternative frame types to stress various execution paths
                frames_fns = [create_fire_frame, create_smoke_frame, create_normal_frame]

                for loop_idx in range(iterations_per_thread):
                    try:
                        frame_fn = frames_fns[loop_idx % len(frames_fns)]
                        frame = frame_fn()

                        pipeline.process_camera_frame(cam_id, frame)
                        local_processed += 1
                    except Exception as e:
                        error_queue.put((thread_idx, loop_idx, str(e)))

                return local_processed

            # 3. Spawn workers and enforce deadlock timeout
            total_dispatched = num_threads * iterations_per_thread
            start_time = time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(worker, i) for i in range(num_threads)]
                # Wait for threads with a timeout. If deadlocked, wait will return unfinished futures
                done, not_done = concurrent.futures.wait(futures, timeout=10.0)

            duration = time.time() - start_time
            deadlock_detected = len(not_done) > 0

            # 4. Gather errors
            crashes = 0
            while not error_queue.empty():
                t_idx, l_idx, err_msg = error_queue.get()
                crashes += 1
                warnings.append(f"Thread {t_idx} Loop {l_idx} failed: {err_msg}")

            # 5. Stop coordinator cleanly
            coordinator.stop()

            # 6. Build report status
            status = "PASSED"
            if deadlock_detected:
                status = "FAILED"
                warnings.append(f"Deadlock detected! {len(not_done)} threads failed to complete within timeout.")
            if crashes > 0:
                status = "FAILED"

            return {
                "status": status,
                "message": f"Stress check finished in {duration:.2f}s.",
                "threads_spawned": num_threads,
                "iterations_per_thread": iterations_per_thread,
                "total_dispatched": total_dispatched,
                "crashes": crashes,
                "deadlock_detected": deadlock_detected,
                "duration_sec": duration,
                "warnings": warnings,
            }

        except Exception as e:
            try:
                coordinator.stop()
            except Exception:
                pass
            return {
                "status": "FAILED",
                "message": f"Stress test setup crash: {e}",
                "threads_spawned": 0,
                "crashes": 1,
                "deadlock_detected": False,
                "warnings": [f"Setup crash: {e}"],
            }
