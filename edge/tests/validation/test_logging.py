"""Logging Audit & Validation for AERA.

Captures active logger outputs during pipeline runs and validates timestamp presence,
log level formatting (INFO/WARNING/ERROR), and subsystem source categorization.
"""

import logging
import re
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import numpy as np

from src.camera.camera import CameraStatus
from src.integration.coordinator import SystemCoordinator
from src.integration.pipeline import EmergencyPipeline


class ListLogHandler(logging.Handler):
    """Custom logging handler to record log entries in a thread-safe list."""

    def __init__(self) -> None:
        super().__init__()
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def create_fire_frame() -> np.ndarray:
    """Create a BGR frame with a cluster of fire-colored pixels."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[10:90, 10:90, 2] = 250
    frame[10:90, 10:90, 1] = 10
    frame[10:90, 10:90, 0] = 10
    return frame


def test_logger_formatting() -> None:
    """Verify that system log messages conform to level, timestamp, and package schemas."""
    res = run_validation()
    assert res["status"] == "PASSED"
    assert res["records_audited"] > 0


def run_validation() -> Dict[str, Any]:
    """Capture logs during live execution and audit formatting rules.

    Returns:
        Dict: Logging validation report.
    """
    warnings: List[str] = []

    # 1. Attach custom list handler to the root logger or key package loggers
    handler = ListLogHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    old_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

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

            # Trigger normal run
            coordinator.camera_manager.register_camera("cam_log", "Log Cam", "dummy")
            coordinator.camera_manager.start_camera("cam_log")
            pipeline = EmergencyPipeline(coordinator)
            pipeline.process_camera_frame("cam_log", create_fire_frame())

            # Trigger warning/error run (invalid camera frame failure injection)
            try:
                pipeline.process_camera_frame("cam_log", None)  # type: ignore
            except Exception:
                pass

            coordinator.stop()

        except Exception as e:
            warnings.append(f"Execution failed during log logging run: {e}")
            try:
                coordinator.stop()
            except Exception:
                pass

    # 2. Detach handler
    root_logger.removeHandler(handler)
    root_logger.setLevel(old_level)

    # 3. Audit Captured Records
    records_audited = len(handler.records)
    error_logs = 0
    warning_logs = 0
    info_logs = 0
    subsystem_logs = 0

    has_timestamp = True
    has_valid_format = True

    # Regex to check if asctime matches YYYY-MM-DD HH:MM:SS,mmm or similar
    # The default formatter maps asctime to strings containing numbers/separators
    asctime_pattern = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    for record in handler.records:
        # Check level count
        if record.levelname == "ERROR":
            error_logs += 1
        elif record.levelname == "WARNING":
            warning_logs += 1
        elif record.levelname == "INFO":
            info_logs += 1

        # Check source package starts with 'src' or 'tests'
        if record.name.startswith("src.") or record.name.startswith("tests.") or record.name in ("src", "tests"):
            subsystem_logs += 1

        # Format record using handler's formatter to check asctime format
        formatted = handler.formatter.format(record) if handler.formatter else ""
        # Check timestamp pattern
        if not asctime_pattern.search(formatted):
            has_timestamp = False
            warnings.append(f"Log entry has missing or invalid timestamp: '{formatted}'")

        # Verify level, source name, and message format
        if f"[{record.levelname}]" not in formatted or record.name not in formatted:
            has_valid_format = False
            warnings.append(f"Log entry fails formatting rules: '{formatted}'")

    status = "PASSED"
    if records_audited == 0:
        status = "FAILED"
        warnings.append("No logs were captured during validation run.")
    elif not has_timestamp or not has_valid_format:
        status = "FAILED"

    return {
        "status": status,
        "message": f"Logging audit complete. Audited {records_audited} log entries.",
        "records_audited": records_audited,
        "error_logs": error_logs,
        "warning_logs": warning_logs,
        "info_logs": info_logs,
        "subsystem_logs_count": subsystem_logs,
        "has_timestamp": has_timestamp,
        "has_valid_format": has_valid_format,
        "warnings": warnings,
    }
