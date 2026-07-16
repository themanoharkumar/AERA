"""ReportFormatter class for the AERA Report Engine.

This module defines the ReportFormatter class, transforming structured DecisionResult
and Evidence details into human-readable report sections.
"""

from datetime import datetime
import time
from typing import Any, Dict

from src.decision.result import DecisionResult
from src.evidence.evidence import Evidence


class ReportFormatter:
    """Transforms raw DecisionResults and Evidence details into standardized, human-readable sections."""

    def format_timestamp(self, timestamp: float) -> str:
        """Convert a float epoch timestamp to a standardized human-readable date string.

        Args:
            timestamp: Epoch float timestamp.

        Returns:
            Formatted datetime string: YYYY-MM-DD HH:MM:SS.
        """
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    def format_severity(self, severity_val: Any) -> str:
        """Translate severity enums or strings into clear, uppercase human-readable levels.

        Args:
            severity_val: Severity level (e.g. DecisionSeverity or string).

        Returns:
            Uppercase string representation of severity.
        """
        if hasattr(severity_val, "value"):
            return str(severity_val.value).upper()
        return str(severity_val).upper()

    def generate_incident_summary(self, decision: DecisionResult, evidence: Evidence) -> str:
        """Generate a concise paragraph detailing the incident summary.

        Args:
            decision: DecisionResult instance containing evaluation data.
            evidence: Evidence instance containing files and metadata.

        Returns:
            Concise incident description summary string.
        """
        action = decision.action.upper()
        severity = self.format_severity(decision.severity)
        reason = decision.reason
        timestamp_str = self.format_timestamp(decision.timestamp)
        return (
            f"At {timestamp_str}, AERA detected a {severity} severity incident. "
            f"The system performed evaluation resulting in action: {action}. "
            f"Reasoning breakdown: {reason}"
        )

    def compile_sections(self, report_id: str, decision: DecisionResult, evidence: Evidence) -> Dict[str, str]:
        """Compile and format all sections required for a template render.

        Args:
            report_id: Unique identifier for the report.
            decision: DecisionResult instance containing evaluation data.
            evidence: Evidence instance containing files and metadata.

        Returns:
            A dictionary containing the keys:
            ['header', 'incident_summary', 'event_information', 'decision_information', 'evidence_information', 'footer']
        """
        camera_id = evidence.metadata.get("camera_id", "UNKNOWN_CAMERA")
        detector_name = evidence.metadata.get("detector_name", "UNKNOWN_DETECTOR")
        res_tuple = evidence.metadata.get("resolution", (0, 0))
        res_str = f"{res_tuple[0]}x{res_tuple[1]}"

        # Header
        header = (
            f"======================================================================\n"
            f"AERA INCIDENT REPORT: {report_id}\n"
            f"======================================================================"
        )

        # Incident Summary
        incident_summary = (
            f"--- INCIDENT SUMMARY ---\n"
            f"{self.generate_incident_summary(decision, evidence)}"
        )

        # Event Information
        event_information = (
            f"--- EVENT DETAILS ---\n"
            f"Event ID: {decision.event_id}\n"
            f"Camera Source ID: {camera_id}\n"
            f"Confidence Score: {decision.confidence:.2%}"
        )

        # Decision Information
        severity = self.format_severity(decision.severity)
        decision_information = (
            f"--- ACTION & DECISION DETAILS ---\n"
            f"Decision ID: {decision.decision_id}\n"
            f"Incident Severity: {severity}\n"
            f"Assigned Response Action: {decision.action.upper()}\n"
            f"Reasoning Details: {decision.reason}"
        )

        # Evidence Information
        evidence_information = (
            f"--- PRESERVED EVIDENCE ---\n"
            f"Evidence Package ID: {evidence.evidence_id}\n"
            f"Detector Engine: {detector_name}\n"
            f"Screenshot Path: {evidence.image_path or 'N/A'}\n"
            f"Video Clip Path: {evidence.video_path or 'N/A'}\n"
            f"Capture Resolution: {res_str}"
        )

        # Footer
        footer = (
            f"Report Generated: {self.format_timestamp(time.time())} (UTC)\n"
            f"======================================================================"
        )

        return {
            "header": header,
            "incident_summary": incident_summary,
            "event_information": event_information,
            "decision_information": decision_information,
            "evidence_information": evidence_information,
            "footer": footer,
        }
