"""Unit tests for the AERA Alert System.

This module contains test cases verifying exception propagation, Alert entity models,
BaseNotifier ABC constraints, ConsoleNotifier formats, AlertHistory logs, and
retry mechanisms in AlertManager.
"""

import time
import concurrent.futures
from typing import List, Dict, Any, Optional
import pytest

from src.alert import (
    Alert,
    AlertError,
    AlertHistory,
    AlertManager,
    BaseNotifier,
    ChannelError,
    ConsoleNotifier,
    HistoryRecord,
    NotificationError,
)
from src.report.report import Report


# ==============================================================================
# 1. Custom Exceptions & Immutability
# ==============================================================================
def test_exceptions_hierarchy() -> None:
    """Verify exceptions inherit from AlertError and carry correct messages."""
    assert issubclass(NotificationError, AlertError)
    assert issubclass(ChannelError, AlertError)

    exc = NotificationError("Delivery failed")
    assert str(exc) == "Delivery failed"
    assert exc.message == "Delivery failed"


def test_alert_immutability() -> None:
    """Verify that Alert dataclass instances are frozen and immutable."""
    alert = Alert(
        alert_id="alt_1",
        report_id="rep_1",
        severity="critical",
        timestamp=time.time(),
        status="success",
        metadata={"channel": "ConsoleNotifier"},
    )

    assert alert.alert_id == "alt_1"
    assert alert.delivery_status == "success"  # alias check

    with pytest.raises(AttributeError):
        alert.alert_id = "alt_2"  # type: ignore


# ==============================================================================
# 2. BaseNotifier ABC Constraints
# ==============================================================================
def test_base_notifier_abc() -> None:
    """Verify BaseNotifier cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseNotifier()  # type: ignore


# ==============================================================================
# 3. ConsoleNotifier
# ==============================================================================
def test_console_notifier_delivery() -> None:
    """Verify ConsoleNotifier checks missing fields and handles delivery."""
    notifier = ConsoleNotifier()
    assert notifier.name == "ConsoleNotifier"

    report_ok = Report(
        report_id="rep_01",
        event_id="evt_01",
        decision_id="dec_01",
        evidence_id="ev_01",
        title="Incident Title",
        summary="Smoke alarm activated",
        timestamp=time.time(),
        metadata={},
    )

    # Valid delivery
    assert notifier.send_notification(report_ok) is True

    # Missing report_id
    report_bad = Report(
        report_id="",
        event_id="evt_01",
        decision_id="dec_01",
        evidence_id="ev_01",
        title="Title",
        summary="Summary",
        timestamp=time.time(),
        metadata={},
    )
    with pytest.raises(NotificationError) as exc:
        notifier.send_notification(report_bad)
    assert "report_id" in str(exc.value)

    # Missing summary
    report_bad_sum = Report(
        report_id="rep_01",
        event_id="evt_01",
        decision_id="dec_01",
        evidence_id="ev_01",
        title="Title",
        summary="",
        timestamp=time.time(),
        metadata={},
    )
    with pytest.raises(NotificationError) as exc:
        notifier.send_notification(report_bad_sum)
    assert "summary" in str(exc.value)


# ==============================================================================
# 4. AlertHistory Tracking
# ==============================================================================
def test_alert_history_operations() -> None:
    """Verify AlertHistory appends records thread-safely and clears correctly."""
    history = AlertHistory()

    now = time.time()
    history.record_delivery(
        alert_id="alt_1",
        timestamp=now,
        channel="ConsoleNotifier",
        status="success",
        retry_count=0,
    )
    history.record_delivery(
        alert_id="alt_1",
        timestamp=now + 5.0,
        channel="ConsoleNotifier",
        status="success",
        retry_count=1,
    )

    records = history.get_history("alt_1")
    assert len(records) == 2
    assert records[0].delivery_status == "success"
    assert records[0].retry_count == 0
    assert records[1].retry_count == 1

    history.clear()
    assert len(history.get_history("alt_1")) == 0


# ==============================================================================
# 5. AlertManager Integrations, Retries, and Concurrency
# ==============================================================================
class FailingNotifier(BaseNotifier):
    """Notifier implementation designed to fail N times before succeeding."""

    def __init__(self, fail_attempts: int, notifier_name: str = "FailingNotifier") -> None:
        self._name = notifier_name
        self.fail_attempts = fail_attempts
        self.attempts = 0

    @property
    def name(self) -> str:
        return self._name

    def validate_payload(self, report: Report) -> None:
        pass

    def send_notification(self, report: Report, metadata: Optional[Dict[str, Any]] = None) -> bool:
        self.attempts += 1
        if self.attempts <= self.fail_attempts:
            raise RuntimeError(f"Simulated failure {self.attempts}/{self.fail_attempts}")
        return True


def test_alert_manager_retry_flow() -> None:
    """Verify AlertManager triggers retries and records delivery status correctly."""
    manager = AlertManager()

    failing_channel = FailingNotifier(fail_attempts=2)
    manager.register_channel(failing_channel)

    report = Report(
        report_id="rep_1",
        event_id="evt_1",
        decision_id="dec_1",
        evidence_id="ev_1",
        title="Incident Title - HIGH",
        summary="High severity alert summary",
        timestamp=time.time(),
        metadata={},
    )

    # 1. Dispatch succeeding after 2 retries (attempt 1 fail, attempt 2 fail, attempt 3 succeeds)
    alert = manager.trigger_alert(
        report,
        channel_name="FailingNotifier",
        max_retries=3,
        retry_delay=0.01,
    )

    assert alert.status == "success"
    assert alert.severity == "HIGH"  # parsed from title
    assert alert.metadata["retry_count"] == 2

    # 2. Dispatch failing permanently (max retries exceeded)
    permanent_fail = FailingNotifier(fail_attempts=5, notifier_name="PermanentFailNotifier")
    manager.register_channel(permanent_fail)

    with pytest.raises(AlertError) as exc:
        manager.trigger_alert(
            report,
            channel_name="PermanentFailNotifier",
            max_retries=2,
            retry_delay=0.01,
        )
    assert "delivery failed" in str(exc.value)

    # Check alert history still records failed dispatches
    logs = manager.history.get_history(exc.value.message.split("'")[1] if hasattr(exc.value, "message") else "")
    # Find records on AlertManager history
    all_alerts = manager.list_alerts()
    # The last logged alert should be failed
    assert all_alerts[-1].status == "failed"
    assert all_alerts[-1].metadata["retry_count"] == 2


def test_alert_manager_concurrency() -> None:
    """Verify AlertManager executes concurrent alert triggers thread-safely."""
    manager = AlertManager()
    num_threads = 10
    num_alerts_per_thread = 5

    report = Report(
        report_id="rep_test",
        event_id="evt_test",
        decision_id="dec_test",
        evidence_id="ev_test",
        title="Report Title",
        summary="AERA incident detail report summary.",
        timestamp=time.time(),
        metadata={"severity": "CRITICAL"},
    )

    def worker(thread_idx: int) -> List[Alert]:
        results: List[Alert] = []
        for i in range(num_alerts_per_thread):
            alert = manager.trigger_alert(
                report,
                channel_name="ConsoleNotifier",
                max_retries=1,
                retry_delay=0.01,
            )
            results.append(alert)
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, idx) for idx in range(num_threads)]
        concurrent.futures.wait(futures)

    all_alerts = manager.list_alerts()
    assert len(all_alerts) == num_threads * num_alerts_per_thread

    # Clear caches
    manager.clear()
    assert len(manager.list_alerts()) == 0
