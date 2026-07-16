"""Backend Subsystems Health Verification for AERA.

Audits active health statuses for the 8 core engines and manager layers
(Camera, Detection, Event, Decision, Evidence, Report, Alert, and Integration).
"""

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import numpy as np

from src.integration.coordinator import SystemCoordinator


def test_system_health() -> None:
    """Verify that all subsystems report healthy status after startup."""
    res = run_validation()
    assert res["status"] == "PASSED"
    assert res["overall_health"] == "healthy"


def run_validation() -> Dict[str, Any]:
    """Execute subsystem health audit compile reports.

    Returns:
        Dict: Subsystem health check report.
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

            # Compile health report from SystemHealthMonitor
            health_report = coordinator.health_monitor.check_health()
            
            # Check individual health entries
            subsystem_mapping = {
                "camera_manager": "camera",
                "detection_pipeline": "detection",
                "event_manager": "event",
                "decision_engine": "decision",
                "evidence_manager": "evidence",
                "report_manager": "report",
                "alert_manager": "alert",
            }

            all_healthy = True
            details: Dict[str, str] = {}

            # Parse health status dict
            for sub_name, report_key in subsystem_mapping.items():
                sub_report = health_report.get("subsystems", {}).get(report_key, {})
                status = sub_report.get("status", "unknown")
                details[sub_name] = status
                if status != "healthy":
                    all_healthy = False
                    warnings.append(f"Subsystem '{sub_name}' reported unhealthy/unknown status: {status}")

            # Integration coordinator state checks
            coordinator_status = "healthy" if coordinator.is_started else "unhealthy"
            details["integration_layer"] = coordinator_status
            if coordinator_status != "healthy":
                all_healthy = False
                warnings.append("Integration coordinator is reported unhealthy/stopped.")

            coordinator.stop()

            # Final status compile
            overall_health = "healthy" if all_healthy else "unhealthy"
            status = "PASSED" if all_healthy else "FAILED"

            return {
                "status": status,
                "overall_health": overall_health,
                "message": "All core AERA subsystems reported healthy.",
                "details": details,
                "warnings": warnings,
            }

        except Exception as e:
            try:
                coordinator.stop()
            except Exception:
                pass
            return {
                "status": "FAILED",
                "overall_health": "unhealthy",
                "message": f"Health check validation crashed: {e}",
                "details": {},
                "warnings": [f"Setup crash: {e}"],
            }
