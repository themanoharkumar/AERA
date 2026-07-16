"""SystemValidator implementation for AERA.

This module validates that all backend subsystem instances are present,
expose the required interfaces, and carry valid config properties.
"""

from typing import Any
from src.integration.exceptions import ValidationError


class SystemValidator:
    """Verifies module compatibility and interface integrity across the AERA platform.

    Uses reflection checks on registered manager and engine instances to confirm
    critical callable entry points exist before triggering pipeline operations.
    """

    def validate_camera_manager(self, camera_manager: Any) -> None:
        """Verify CameraManager exposes required lifecycle operations.

        Args:
            camera_manager: Instance to check.

        Raises:
            ValidationError: If interface is missing expected operations.
        """
        if camera_manager is None:
            raise ValidationError("CameraManager is not provided (None).")

        required_methods = ["register_camera", "remove_camera", "start_camera", "stop_camera", "get_frame", "list_cameras", "shutdown"]
        for method in required_methods:
            if not hasattr(camera_manager, method) or not callable(getattr(camera_manager, method)):
                raise ValidationError(
                    f"CameraManager interface validation failed: missing method '{method}'."
                )

    def validate_detection_pipeline(self, detection_pipeline: Any) -> None:
        """Verify DetectionPipeline exposes required processing operations.

        Args:
            detection_pipeline: Instance to check.

        Raises:
            ValidationError: If interface is missing expected operations.
        """
        if detection_pipeline is None:
            raise ValidationError("DetectionPipeline is not provided (None).")

        required_methods = ["process_frame"]
        for method in required_methods:
            if not hasattr(detection_pipeline, method) or not callable(getattr(detection_pipeline, method)):
                raise ValidationError(
                    f"DetectionPipeline interface validation failed: missing method '{method}'."
                )

    def validate_event_manager(self, event_manager: Any) -> None:
        """Verify EventManager exposes required CRUD/lifecycle operations.

        Args:
            event_manager: Instance to check.

        Raises:
            ValidationError: If interface is missing expected operations.
        """
        if event_manager is None:
            raise ValidationError("EventManager is not provided (None).")

        required_methods = ["create_event", "register_event", "get_event", "list_events", "clear_events"]
        for method in required_methods:
            if not hasattr(event_manager, method) or not callable(getattr(event_manager, method)):
                raise ValidationError(
                    f"EventManager interface validation failed: missing method '{method}'."
                )

    def validate_decision_engine(self, decision_engine: Any) -> None:
        """Verify DecisionEngine exposes required evaluation operations.

        Args:
            decision_engine: Instance to check.

        Raises:
            ValidationError: If interface is missing expected operations.
        """
        if decision_engine is None:
            raise ValidationError("DecisionEngine is not provided (None).")

        required_methods = ["evaluate_event", "clear"]
        for method in required_methods:
            if not hasattr(decision_engine, method) or not callable(getattr(decision_engine, method)):
                raise ValidationError(
                    f"DecisionEngine interface validation failed: missing method '{method}'."
                )

    def validate_evidence_manager(self, evidence_manager: Any) -> None:
        """Verify EvidenceManager exposes required evidence packaging operations.

        Args:
            evidence_manager: Instance to check.

        Raises:
            ValidationError: If interface is missing expected operations.
        """
        if evidence_manager is None:
            raise ValidationError("EvidenceManager is not provided (None).")

        required_methods = ["create_evidence", "get_evidence", "list_evidence", "clear"]
        for method in required_methods:
            if not hasattr(evidence_manager, method) or not callable(getattr(evidence_manager, method)):
                raise ValidationError(
                    f"EvidenceManager interface validation failed: missing method '{method}'."
                )

    def validate_report_manager(self, report_manager: Any) -> None:
        """Verify ReportManager exposes required templating and exporting operations.

        Args:
            report_manager: Instance to check.

        Raises:
            ValidationError: If interface is missing expected operations.
        """
        if report_manager is None:
            raise ValidationError("ReportManager is not provided (None).")

        required_methods = ["generate_report", "get_report", "list_reports", "clear"]
        for method in required_methods:
            if not hasattr(report_manager, method) or not callable(getattr(report_manager, method)):
                raise ValidationError(
                    f"ReportManager interface validation failed: missing method '{method}'."
                )

    def validate_alert_manager(self, alert_manager: Any) -> None:
        """Verify AlertManager exposes required notification routing operations.

        Args:
            alert_manager: Instance to check.

        Raises:
            ValidationError: If interface is missing expected operations.
        """
        if alert_manager is None:
            raise ValidationError("AlertManager is not provided (None).")

        required_methods = ["register_channel", "trigger_alert", "get_alert", "list_alerts", "clear"]
        for method in required_methods:
            if not hasattr(alert_manager, method) or not callable(getattr(alert_manager, method)):
                raise ValidationError(
                    f"AlertManager interface validation failed: missing method '{method}'."
                )

    def validate_system(
        self,
        camera_manager: Any,
        detection_pipeline: Any,
        event_manager: Any,
        decision_engine: Any,
        evidence_manager: Any,
        report_manager: Any,
        alert_manager: Any,
    ) -> None:
        """Audit all backend subsystems compatibility and dependency integrity.

        Args:
            camera_manager: CameraManager instance.
            detection_pipeline: DetectionPipeline instance.
            event_manager: EventManager instance.
            decision_engine: DecisionEngine instance.
            evidence_manager: EvidenceManager instance.
            report_manager: ReportManager instance.
            alert_manager: AlertManager instance.

        Raises:
            ValidationError: If any subsystem interface fails audit.
        """
        self.validate_camera_manager(camera_manager)
        self.validate_detection_pipeline(detection_pipeline)
        self.validate_event_manager(event_manager)
        self.validate_decision_engine(decision_engine)
        self.validate_evidence_manager(evidence_manager)
        self.validate_report_manager(report_manager)
        self.validate_alert_manager(alert_manager)
