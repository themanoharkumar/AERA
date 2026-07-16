"""Unit tests for the AERA Report Engine.

This module contains test cases verifying exception propagation, Report entity models,
ReportTemplate rendering, ReportFormatter compilations, JSONExporter output validation,
and concurrent generation routines in ReportManager.
"""

import time
import json
import concurrent.futures
from typing import List, Dict, Any
import pytest

from src.decision import DecisionResult, DecisionSeverity
from src.evidence import Evidence
from src.report import (
    BaseExporter,
    JSONExporter,
    Report,
    ReportError,
    ReportFormatter,
    ReportManager,
    ReportTemplate,
    TemplateError,
    ExportError,
)


# ==============================================================================
# 1. Custom Exceptions & Immutability
# ==============================================================================
def test_exceptions_hierarchy() -> None:
    """Verify exceptions inherit from ReportError and carry correct messages."""
    assert issubclass(TemplateError, ReportError)
    assert issubclass(ExportError, ReportError)

    exc = TemplateError("Layout rendering failed")
    assert str(exc) == "Layout rendering failed"
    assert exc.message == "Layout rendering failed"


def test_report_immutability() -> None:
    """Verify that Report dataclass instances are frozen and immutable."""
    report = Report(
        report_id="rep_1",
        event_id="evt_1",
        decision_id="dec_1",
        evidence_id="ev_1",
        title="Incident Report",
        summary="AERA incident detected.",
        timestamp=time.time(),
        metadata={"camera_id": "cam_1"},
    )

    assert report.report_id == "rep_1"
    with pytest.raises(AttributeError):
        report.report_id = "rep_2"  # type: ignore


# ==============================================================================
# 2. ReportTemplate
# ==============================================================================
def test_report_template_rendering() -> None:
    """Verify ReportTemplate orders sections deterministically and handles errors."""
    template = ReportTemplate(name="Test Template")
    assert template.name == "Test Template"

    sections = {
        "header": "HEADER",
        "incident_summary": "SUMMARY",
        "event_information": "EVENT",
        "decision_information": "DECISION",
        "evidence_information": "EVIDENCE",
        "footer": "FOOTER",
    }

    # Render successfully
    rendered = template.render(sections)
    assert "HEADER\n\nSUMMARY\n\nEVENT\n\nDECISION\n\nEVIDENCE\n\nFOOTER" in rendered

    # Render fails with missing sections
    bad_sections = {"header": "HEADER"}
    with pytest.raises(TemplateError) as exc:
        template.render(bad_sections)
    assert "Missing required sections" in str(exc.value)

    # Empty sections check
    with pytest.raises(TemplateError) as exc:
        template.render({})
    assert "cannot be empty" in str(exc.value)


# ==============================================================================
# 3. ReportFormatter
# ==============================================================================
def test_report_formatter_formatting() -> None:
    """Verify ReportFormatter normalizes severities, dates, and maps variables."""
    formatter = ReportFormatter()

    # Timestamp conversion
    t_str = formatter.format_timestamp(1719876543.0)
    assert "2024-07-02" in t_str

    # Severity normalization
    assert formatter.format_severity("critical") == "CRITICAL"
    assert formatter.format_severity(DecisionSeverity.HIGH) == "HIGH"

    # Compile sections variables check
    decision = DecisionResult(
        decision_id="dec_01",
        event_id="evt_01",
        severity=DecisionSeverity.CRITICAL,
        action="escalate",
        reason="Active fire detected on source stream.",
        confidence=0.98,
        timestamp=1719876543.0,
        metadata={},
    )
    evidence = Evidence(
        evidence_id="ev_01",
        event_id="evt_01",
        decision_id="dec_01",
        image_path="/local/path/img.jpg",
        video_path="",
        timestamp=1719876543.0,
        metadata={"camera_id": "cam_23", "detector_name": "FireModel", "resolution": (1920, 1080)},
    )

    compiled = formatter.compile_sections("rep_01", decision, evidence)
    assert compiled["header"].startswith("=======================================")
    assert "cam_23" in compiled["event_information"]
    assert "FireModel" in compiled["evidence_information"]
    assert "1920x1080" in compiled["evidence_information"]
    assert "98.00%" in compiled["event_information"]


# ==============================================================================
# 4. BaseExporter ABC & JSONExporter
# ==============================================================================
def test_base_exporter_abc() -> None:
    """Verify BaseExporter cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseExporter()  # type: ignore


def test_json_exporter() -> None:
    """Verify JSONExporter serializes Report objects to JSON format strings."""
    exporter = JSONExporter()

    report = Report(
        report_id="rep_1",
        event_id="evt_1",
        decision_id="dec_1",
        evidence_id="ev_1",
        title="Title",
        summary="Summary",
        timestamp=1719876543.0,
        metadata={"custom": "val"},
    )

    # Valid export
    json_str = exporter.export(report)
    parsed = json.loads(json_str)
    assert parsed["report_id"] == "rep_1"
    assert parsed["metadata"] == {"custom": "val"}

    # Invalid None check
    with pytest.raises(ExportError):
        exporter.export(None)  # type: ignore


# ==============================================================================
# 5. ReportManager Coordination & Concurrency
# ==============================================================================
def test_report_manager_e2e() -> None:
    """Verify ReportManager generates, caches, and exports reports."""
    manager = ReportManager()

    decision = DecisionResult(
        decision_id="dec_01",
        event_id="evt_01",
        severity=DecisionSeverity.CRITICAL,
        action="escalate",
        reason="Fire alarm triggered",
        confidence=0.95,
        timestamp=time.time(),
        metadata={},
    )
    evidence = Evidence(
        evidence_id="ev_01",
        event_id="evt_01",
        decision_id="dec_01",
        image_path="/path/img.jpg",
        video_path="/path/clip.mp4",
        timestamp=time.time(),
        metadata={"camera_id": "cam_1", "detector_name": "FireDetector", "resolution": (1280, 720)},
    )

    # 1. Generate Report
    report = manager.generate_report(decision, evidence)
    assert report.event_id == "evt_01"
    assert "AERA INCIDENT REPORT" in report.summary
    assert report.metadata["camera_id"] == "cam_1"

    # 2. Retrieve Report
    assert manager.get_report(report.report_id) == report
    assert manager.list_reports() == [report]

    # 3. Export Report
    json_out = manager.export_report(report.report_id)
    parsed = json.loads(json_out)
    assert parsed["report_id"] == report.report_id

    # 4. Exporting missing report raises error
    with pytest.raises(ReportError):
        manager.export_report("missing_id")

    # 5. Missing params validation
    with pytest.raises(ReportError):
        manager.generate_report(None, evidence)  # type: ignore

    # 6. Clear cache
    manager.clear()
    assert len(manager.list_reports()) == 0


def test_report_manager_concurrency() -> None:
    """Verify ReportManager handles concurrent report generation requests thread-safely."""
    manager = ReportManager()
    num_threads = 10
    num_reports_per_thread = 5

    def worker(thread_idx: int) -> List[Report]:
        results: List[Report] = []
        for i in range(num_reports_per_thread):
            decision = DecisionResult(
                decision_id=f"dec_t{thread_idx}_r{i}",
                event_id=f"evt_t{thread_idx}_r{i}",
                severity=DecisionSeverity.MEDIUM,
                action="monitor",
                reason=f"Incident thread {thread_idx} report {i}",
                confidence=0.88,
                timestamp=time.time(),
                metadata={},
            )
            evidence = Evidence(
                evidence_id=f"ev_t{thread_idx}_r{i}",
                event_id=f"evt_t{thread_idx}_r{i}",
                decision_id=f"dec_t{thread_idx}_r{i}",
                image_path="img.jpg",
                video_path="",
                timestamp=time.time(),
                metadata={"camera_id": "cam_concurrent"},
            )
            report = manager.generate_report(decision, evidence)
            results.append(report)
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, idx) for idx in range(num_threads)]
        concurrent.futures.wait(futures)

    all_reports: List[Report] = []
    for f in futures:
        all_reports.extend(f.result())

    assert len(all_reports) == num_threads * num_reports_per_thread
    assert len(manager.list_reports()) == num_threads * num_reports_per_thread
