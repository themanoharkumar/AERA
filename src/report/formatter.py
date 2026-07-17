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

    def generate_operator_report(self, decision: DecisionResult, evidence: Evidence, incident_number: str) -> str:
        """Generate a concise, professional, and actionable report format for operators and Telegram.

        Args:
            decision: The validated DecisionResult.
            evidence: The corresponding Evidence package.
            incident_number: Unique sequential human-friendly incident number.

        Returns:
            Concise, emoji-enriched formatted Operator report.
        """
        # 1. Date and Time
        dt = datetime.fromtimestamp(decision.timestamp)
        date_str = dt.strftime("%d %B %Y")
        time_str = dt.strftime("%H:%M:%S UTC")

        # 2. Incident label
        custom_meta = evidence.metadata.get("custom_metadata", {}) if isinstance(evidence.metadata, dict) else getattr(evidence.metadata, "custom_metadata", {})
        label = custom_meta.get("label", "suspicious activity")
        incident_type = f"{label.capitalize()} Detected" if "detected" not in label.lower() else label.capitalize()

        # 3. Severity formatting
        raw_severity = self.format_severity(decision.severity)
        severity_map = {
            "LOW": "🟢 LOW",
            "MEDIUM": "🟡 MEDIUM",
            "HIGH": "🔴 HIGH",
            "CRITICAL": "🚨 CRITICAL"
        }
        severity_str = severity_map.get(raw_severity, raw_severity)

        # 4. Camera source lookup
        camera_name = custom_meta.get("camera_name")
        if not camera_name:
            camera_name = evidence.metadata.get("camera_id") if isinstance(evidence.metadata, dict) else getattr(evidence.metadata, "camera_id", None)
        if not camera_name:
            camera_name = "webcam_0"

        # 5. Detection Confidence
        confidence_pct = f"{decision.confidence:.0%}"

        # 6. Natural Language Summary and Action mapping
        action_raw = decision.action.upper()
        action_map = {
            "ESCALATE": "ESCALATED",
            "LOG": "LOGGED",
            "RESOLVE": "RESOLVED",
            "IGNORE": "IGNORED",
            "NOTIFY": "NOTIFIED"
        }
        action_str = action_map.get(action_raw, action_raw)
        
        summary_text = (
            f"AERA detected {label.lower()} with a confidence level of {confidence_pct}. "
            f"Because the event exceeded the {raw_severity} severity threshold, "
            f"AERA automatically {action_str.lower()} the incident for immediate attention."
        )

        # 7. Recommended Actions
        actions = []
        if "fire" in label.lower() or "smoke" in label.lower():
            actions = [
                "• Inspect affected location immediately",
                "• Notify emergency personnel",
                "• Prepare evacuation if hazard increases"
            ]
        elif "fall" in label.lower():
            actions = [
                "• Verify person consciousness and breathing",
                "• Administer first aid if trained",
                "• Call medical emergency dispatch if needed"
            ]
        elif "intrusion" in label.lower():
            actions = [
                "• Check secure area locks and door sensors",
                "• Review live camera streams",
                "• Alert security guard/police responders"
            ]
        else:
            actions = [
                "• Monitor camera source live stream",
                "• Dispatch an inspector to check the location",
                "• Verify event details in backend archives"
            ]
        actions_str = "\n".join(actions)

        # 8. Evidence status checks (no Windows paths!)
        has_screenshot = bool(evidence.image_path)
        has_video = bool(evidence.video_path)
        screenshot_status = "✅ Screenshot Attached" if has_screenshot else "❌ Screenshot Not Available"
        video_status = "✅ Video Clip Attached" if has_video else "❌ Video Clip Not Available"

        # 9. Format Operator Report
        op_report = (
            f"══════════════════════════════════════\n"
            f"🚨 AERA INCIDENT REPORT\n"
            f"══════════════════════════════════════\n"
            f"Incident ID\n"
            f"{incident_number}\n\n"
            f"Date\n"
            f"{date_str}\n\n"
            f"Time\n"
            f"{time_str}\n\n"
            f"Incident\n"
            f"{incident_type}\n\n"
            f"Severity\n"
            f"{severity_str}\n\n"
            f"Camera\n"
            f"{camera_name}\n\n"
            f"Detection Confidence\n"
            f"{confidence_pct}\n"
            f"────────────────────────────\n"
            f"Summary\n"
            f"{summary_text}\n"
            f"────────────────────────────\n"
            f"Recommended Actions\n"
            f"{actions_str}\n"
            f"────────────────────────────\n"
            f"Evidence\n"
            f"{screenshot_status}\n"
            f"✅ Incident Report Attached\n"
            f"{video_status}\n"
            f"────────────────────────────\n"
            f"System Action\n"
            f"{action_str}\n"
            f"────────────────────────────\n"
            f"Generated by\n"
            f"AERA AI Emergency Response Assistant\n"
            f"Report Version 1.0\n"
            f"══════════════════════════════════════"
        )
        return op_report

