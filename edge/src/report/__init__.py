"""AERA Report Engine package.

This package exposes incident reporting layers, formats pre-defined layouts,
normalizes dates/severities, and exports JSON string payloads.
"""

from src.report.exceptions import ExportError, ReportError, TemplateError
from src.report.exporter import BaseExporter, JSONExporter
from src.report.formatter import ReportFormatter
from src.report.manager import ReportManager
from src.report.report import Report
from src.report.template import ReportTemplate

__all__ = [
    "Report",
    "ReportManager",
    "ReportTemplate",
    "ReportFormatter",
    "BaseExporter",
    "JSONExporter",
    "ReportError",
    "TemplateError",
    "ExportError",
]
