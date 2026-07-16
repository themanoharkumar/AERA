"""
TEST 7 — Logging Validation
============================
Validates that AERA subsystems produce structured log output through
Python's logging framework and that no bare print() calls leak into
the production source tree.
"""

import logging
import pathlib

import pytest

from src.integration import PipelineError


# ── helpers ──────────────────────────────────────────────────────────

def _is_bare_print(line: str) -> bool:
    """Return True if *line* contains a bare ``print(`` call outside a comment."""
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return False
    # Ignore lines where 'print(' appears only after a '#' comment marker
    code_part = line.split("#", 1)[0]
    return "print(" in code_part


# ── tests ────────────────────────────────────────────────────────────

class TestLoggingValidation:
    """Suite 7 – Logging validation."""

    def test_log_records_have_module_names(
        self, caplog, pipeline, registered_camera, fire_frame
    ):
        """Processing a frame should emit DEBUG+ records from ≥2 distinct
        ``src.*`` loggers."""
        with caplog.at_level(logging.DEBUG):
            pipeline.process_camera_frame(registered_camera, fire_frame)

        src_loggers = {
            r.name for r in caplog.records if r.name.startswith("src.")
        }
        assert len(src_loggers) >= 2, (
            f"Expected ≥2 distinct 'src.*' loggers, got {src_loggers}"
        )

    def test_error_conditions_produce_error_logs(
        self, caplog, pipeline, registered_camera
    ):
        """Passing a ``None`` frame should raise ``PipelineError`` and
        produce at least one ERROR-level log record."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(PipelineError):
                pipeline.process_camera_frame(registered_camera, None)

        error_records = [
            r for r in caplog.records if r.levelno >= logging.ERROR
        ]
        assert len(error_records) >= 1, "Expected ≥1 ERROR log record"

    def test_warning_on_double_start(self, caplog, coordinator):
        """Starting an already-running coordinator should emit a WARNING
        mentioning 'already started'."""
        with caplog.at_level(logging.WARNING):
            coordinator.start()

        warning_records = [
            r
            for r in caplog.records
            if r.levelno >= logging.WARNING
            and "already started" in r.message.lower()
        ]
        assert len(warning_records) >= 1, (
            "Expected a WARNING record mentioning 'already started'"
        )

    def test_no_print_statements_in_source(self):
        """No production ``.py`` file under ``src/`` should contain bare
        ``print()`` calls."""
        src_root = pathlib.Path(r"d:/PROJECTS/AERA/src")
        violations: list[str] = []

        for py_file in src_root.rglob("*.py"):
            for lineno, line in enumerate(
                py_file.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if _is_bare_print(line):
                    violations.append(f"{py_file}:{lineno}: {line.strip()}")

        assert violations == [], (
            "Bare print() calls found in source:\n"
            + "\n".join(violations)
        )
