"""Report exporters definitions for AERA.

This module defines the BaseExporter interface and the concrete JSONExporter,
supporting modular export formats for incident reports.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict
import json
import logging

from src.report.exceptions import ExportError
from src.report.report import Report

logger = logging.getLogger(__name__)


class BaseExporter(ABC):
    """Abstract base class for report exporters.

    Enables ReportManager to remain decoupled from serialization formats.
    """

    @abstractmethod
    def export(self, report: Report) -> str:
        """Export a Report instance to a formatted string.

        Args:
            report: The Report object to serialize.

        Returns:
            The exported report representation as a string.

        Raises:
            ExportError: If exporting fails.
        """
        pass


class JSONExporter(BaseExporter):
    """Concrete exporter implementation serializing Report instances to JSON format."""

    def export(self, report: Report) -> str:
        """Serialize a Report object into a JSON formatted string.

        Args:
            report: The Report object to serialize.

        Returns:
            A JSON-formatted string representation of the report.

        Raises:
            ExportError: If serialization fails.
        """
        if report is None:
            raise ExportError("Cannot export a None report object.")

        try:
            report_dict = asdict(report)
            return json.dumps(report_dict, indent=4)
        except Exception as e:
            logger.exception("Failed to export Report %s to JSON", report.report_id)
            raise ExportError(f"JSON export failed: {e}") from e
