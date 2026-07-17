"""ReportManager coordination layer for AERA.

This module defines the ReportManager class, which coordinates formatting,
template rendering, memory-caching, and exporting of incident reports.
"""

import logging
import threading
import time
import uuid
from typing import Dict, List, Optional

from src.decision.result import DecisionResult
from src.evidence.evidence import Evidence
from src.report.exceptions import ReportError
from src.report.exporter import BaseExporter, JSONExporter
from src.report.formatter import ReportFormatter
from src.report.report import Report
from src.report.template import ReportTemplate

logger = logging.getLogger(__name__)


class ReportManager:
    """Coordinates the generation, retrieval, and exporting of incident reports.

    Implements thread-safe caching and integrates template formatters with exporters.
    """

    def __init__(
        self,
        formatter: Optional[ReportFormatter] = None,
        template: Optional[ReportTemplate] = None,
        exporter: Optional[BaseExporter] = None,
    ) -> None:
        """Initialize the ReportManager.

        Args:
            formatter: Optional custom ReportFormatter. Defaults to standard formatter.
            template: Optional custom ReportTemplate. Defaults to standard template.
            exporter: Optional custom BaseExporter. Defaults to JSONExporter.
        """
        self.formatter = formatter if formatter is not None else ReportFormatter()
        self.template = template if template is not None else ReportTemplate()
        self.exporter = exporter if exporter is not None else JSONExporter()

        self._reports: Dict[str, Report] = {}
        self._lock = threading.Lock()

    def generate_report(self, decision: DecisionResult, evidence: Evidence) -> Report:
        """Generate a standardized incident report from DecisionResult and Evidence.

        Args:
            decision: Validated DecisionResult containing urgency levels and evaluations.
            evidence: Evidence package referencing stored assets and metadata.

        Returns:
            The created immutable Report instance.

        Raises:
            ReportError: If evaluations or evidence are missing or invalid.
        """
        if decision is None:
            raise ReportError("DecisionResult cannot be None.")
        if evidence is None:
            raise ReportError("Evidence package cannot be None.")

        # Ensure matching Event IDs
        if decision.event_id != evidence.event_id:
            logger.warning(
                "Event ID mismatch between DecisionResult (%s) and Evidence (%s)",
                decision.event_id,
                evidence.event_id,
            )

        try:
            report_id = str(uuid.uuid4())
            now_time = time.time()

            # Generate sequential incident number thread-safely
            with self._lock:
                incident_number = self._generate_incident_number(now_time)

            # 1. Compile formatted text sections
            sections = self.formatter.compile_sections(report_id, decision, evidence)

            # 2. Render summary plain text using template (Forensic Report)
            rendered_summary = self.template.render(sections)

            # Generate Operator Report
            operator_summary = self.formatter.generate_operator_report(decision, evidence, incident_number)

            # 3. Determine severity title
            severity_str = self.formatter.format_severity(decision.severity)
            title = f"AERA Emergency Incident Report - {severity_str}"

            # 4. Define metadata
            metadata = {
                "camera_id": evidence.metadata.get("camera_id", "UNKNOWN_CAMERA") if isinstance(evidence.metadata, dict) else getattr(evidence.metadata, "camera_id", "UNKNOWN_CAMERA"),
                "detector_name": evidence.metadata.get("detector_name", "UNKNOWN_DETECTOR") if isinstance(evidence.metadata, dict) else getattr(evidence.metadata, "detector_name", "UNKNOWN_DETECTOR"),
                "template_name": self.template.name,
                "generated_at": now_time,
                "incident_number": incident_number,
            }

            # 5. Construct final Report entity
            report = Report(
                report_id=report_id,
                event_id=decision.event_id,
                decision_id=decision.decision_id,
                evidence_id=evidence.evidence_id,
                title=title,
                summary=rendered_summary,
                timestamp=now_time,
                metadata=metadata,
                operator_summary=operator_summary,
                incident_number=incident_number,
            )

            # 6. Cache report thread-safely
            with self._lock:
                self._reports[report_id] = report

            logger.info("Report %s successfully generated for event %s", report_id, decision.event_id)
            return report

        except Exception as e:
            if isinstance(e, ReportError):
                raise
            logger.exception("Unexpected error compiling report for event %s", decision.event_id)
            raise ReportError(f"Report generation failed: {e}") from e

    def get_report(self, report_id: str) -> Optional[Report]:
        """Retrieve a generated report from cache.

        Args:
            report_id: Unique report identifier.

        Returns:
            The Report object if cached, otherwise None.
        """
        with self._lock:
            return self._reports.get(report_id)

    def list_reports(self) -> List[Report]:
        """Get a copy list of all cached incident reports.

        Returns:
            List of Report objects.
        """
        with self._lock:
            return list(self._reports.values())

    def export_report(self, report_id: str, exporter: Optional[BaseExporter] = None) -> str:
        """Export a cached report to a serialized format using the specified exporter.

        Args:
            report_id: Unique report identifier.
            exporter: Optional custom exporter to override the default exporter.

        Returns:
            The serialized report representation as string.

        Raises:
            ReportError: If the report ID is not found or serializing fails.
        """
        report = self.get_report(report_id)
        if not report:
            raise ReportError(f"Report ID '{report_id}' not found in cache for export.")

        active_exporter = exporter if exporter is not None else self.exporter
        try:
            return active_exporter.export(report)
        except Exception as e:
            logger.exception("Failed to export report %s", report_id)
            raise ReportError(f"Report export failed: {e}") from e

    def clear(self) -> None:
        """Wipe all cached reports from the manager memory."""
        with self._lock:
            self._reports.clear()
            logger.info("ReportManager cache cleared.")

    def _generate_incident_number(self, timestamp: float) -> str:
        """Dynamically generate a sequential human-friendly incident ID.

        Must be called under self._lock context.
        """
        from datetime import datetime
        # Date in format YYYYMMDD
        date_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d")
        today_prefix = f"INC-{date_str}-"
        
        count = 1
        for r in self._reports.values():
            if r.incident_number and r.incident_number.startswith(today_prefix):
                try:
                    num = int(r.incident_number.split("-")[-1])
                    if num >= count:
                        count = num + 1
                except ValueError:
                    pass
        return f"{today_prefix}{count:05d}"
