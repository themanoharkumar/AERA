"""Performance Benchmarking Validation for AERA.

Measures processing latencies across all emergency response pipeline stages
(detection, decision, evidence, report, alert) and calculates summary stats and FPS.
"""

import time
import statistics
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import numpy as np
import cv2
from src.camera.camera import CameraStatus
from src.event.types import EventType
from src.event.priority import EventPriority
from src.evidence.metadata import EvidenceMetadata
from src.integration.coordinator import SystemCoordinator


def create_fire_frame() -> np.ndarray:
    """Create a BGR frame with a cluster of fire-colored pixels."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[10:90, 10:90, 2] = 250
    frame[10:90, 10:90, 1] = 10
    frame[10:90, 10:90, 0] = 10
    return frame


def calculate_stats(latencies: List[float]) -> Dict[str, float]:
    """Calculate summary statistics for a list of latency measurements in ms."""
    if not latencies:
        return {"avg": 0.0, "min": 0.0, "max": 0.0, "stddev": 0.0}
    
    # Convert seconds to milliseconds
    ms_values = [x * 1000.0 for x in latencies]
    
    avg_val = sum(ms_values) / len(ms_values)
    stddev_val = statistics.stdev(ms_values) if len(ms_values) > 1 else 0.0
    
    return {
        "avg_ms": avg_val,
        "min_ms": min(ms_values),
        "max_ms": max(ms_values),
        "stddev_ms": stddev_val,
    }


def test_performance_benchmark_run() -> None:
    """Verify that a brief performance benchmark executes without failure."""
    res = run_validation(iterations=3)
    assert res["status"] == "PASSED"
    assert "metrics" in res
    assert res["metrics"]["pipeline_total"]["avg_ms"] > 0.0


def run_validation(iterations: int = 10) -> Dict[str, Any]:
    """Benchmark subsystem latencies and calculate FPS and averages.

    Args:
        iterations: Number of pipeline loops to run.

    Returns:
        Dict: Performance benchmark report.
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
            camera_id = "cam_perf"
            coordinator.camera_manager.register_camera(
                camera_id=camera_id,
                name="Performance Test Camera",
                source="dummy_perf",
            )
            coordinator.camera_manager.start_camera(camera_id)

            frame = create_fire_frame()

            # Latency metric buckets
            latencies_detect: List[float] = []
            latencies_event: List[float] = []
            latencies_decision: List[float] = []
            latencies_evidence: List[float] = []
            latencies_report: List[float] = []
            latencies_alert: List[float] = []
            latencies_total: List[float] = []

            # Dry run to warm up caches
            coordinator.detection_pipeline.process_frame(frame)

            for _ in range(iterations):
                t_total_start = time.perf_counter()

                # 1. Detection Stage
                t0 = time.perf_counter()
                detection_results = coordinator.detection_pipeline.process_frame(frame)
                latencies_detect.append(time.perf_counter() - t0)

                if not detection_results:
                    continue
                result = detection_results[0]

                # 2. Event Manager Stage
                t0 = time.perf_counter()
                event = coordinator.event_manager.create_event(
                    event_type=EventType.FIRE,
                    camera_id=camera_id,
                    description="AI detection fire",
                    confidence=result.confidence,
                    priority=EventPriority.CRITICAL,
                    metadata=result.metadata,
                )
                latencies_event.append(time.perf_counter() - t0)

                # 3. Decision Engine Stage
                t0 = time.perf_counter()
                decision = coordinator.decision_engine.evaluate_event(event)
                latencies_decision.append(time.perf_counter() - t0)

                # 4. Evidence Storage Stage (simulating pipeline capture)
                t0 = time.perf_counter()
                ret, jpeg_bytes = cv2.imencode(".jpg", frame)
                image_bytes = jpeg_bytes.tobytes() if ret else b""
                evidence_metadata = EvidenceMetadata(
                    camera_id=camera_id,
                    event_id=event.event_id,
                    decision_id=decision.decision_id,
                    timestamp=time.time(),
                    detector_name=result.detector_name,
                    file_size=len(image_bytes),
                    resolution=(frame.shape[1], frame.shape[0])
                    if len(frame.shape) >= 2
                    else (0, 0),
                    custom_metadata={
                        "detector_confidence": result.confidence,
                        "label": result.label,
                    },
                )
                evidence = coordinator.evidence_manager.create_evidence(
                    event_id=event.event_id,
                    decision_id=decision.decision_id,
                    metadata=evidence_metadata,
                    image_data=image_bytes,
                )
                latencies_evidence.append(time.perf_counter() - t0)

                # 5. Report Compilation Stage
                t0 = time.perf_counter()
                report = coordinator.report_manager.generate_report(decision, evidence)
                latencies_report.append(time.perf_counter() - t0)

                # 6. Alert System Stage
                t0 = time.perf_counter()
                coordinator.alert_manager.trigger_alert(report)
                latencies_alert.append(time.perf_counter() - t0)

                latencies_total.append(time.perf_counter() - t_total_start)

            coordinator.stop()

            # Compile stats
            metrics = {
                "detection": calculate_stats(latencies_detect),
                "event": calculate_stats(latencies_event),
                "decision": calculate_stats(latencies_decision),
                "evidence": calculate_stats(latencies_evidence),
                "report": calculate_stats(latencies_report),
                "alert": calculate_stats(latencies_alert),
                "pipeline_total": calculate_stats(latencies_total),
            }

            # Calculate throughput (FPS) based on average total latency
            avg_sec = metrics["pipeline_total"]["avg_ms"] / 1000.0
            avg_fps = 1.0 / avg_sec if avg_sec > 0 else 0.0

            return {
                "status": "PASSED",
                "message": f"Performance benchmark completed over {iterations} loops.",
                "avg_fps": avg_fps,
                "metrics": metrics,
                "warnings": warnings,
            }

        except Exception as e:
            try:
                coordinator.stop()
            except Exception:
                pass
            return {
                "status": "FAILED",
                "message": f"Performance benchmarking crashed: {e}",
                "avg_fps": 0.0,
                "metrics": {},
                "warnings": [f"Benchmark crash: {e}"],
            }
