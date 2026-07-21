"""Unit tests for the AERA Decision Engine.

This module contains test cases verifying exception propagation, DecisionResult models,
DecisionSeverity enums, DecisionPolicy parameters, custom and concrete BaseRule subclasses,
and thread-safe DecisionEngine evaluation flow.
"""

import time
import concurrent.futures
from typing import List, Dict, Any
import pytest

from src.decision import (
    BaseRule,
    DecisionEngine,
    DecisionError,
    DecisionPolicy,
    DecisionResult,
    DecisionSeverity,
    PolicyError,
    RuleExecutionError,
    ActionDeterminationRule,
    ConfidenceThresholdRule,
    DuplicateSuppressionRule,
    SeverityCalculationRule,
)
from src.event.event import Event
from src.event.priority import EventPriority
from src.event.status import EventStatus
from src.event.types import EventType


# ==============================================================================
# 1. Test Custom Exceptions & Enums
# ==============================================================================
def test_exceptions_hierarchy() -> None:
    """Verify exceptions inherit from DecisionError and support custom messages."""
    assert issubclass(RuleExecutionError, DecisionError)
    assert issubclass(PolicyError, DecisionError)

    exc = PolicyError("Invalid window")
    assert str(exc) == "Invalid window"
    assert exc.message == "Invalid window"


def test_severity_values() -> None:
    """Verify DecisionSeverity enums map to correct lowercase values."""
    assert DecisionSeverity.LOW.value == "low"
    assert DecisionSeverity.MEDIUM.value == "medium"
    assert DecisionSeverity.HIGH.value == "high"
    assert DecisionSeverity.CRITICAL.value == "critical"


# ==============================================================================
# 2. Test DecisionResult
# ==============================================================================
def test_decision_result_initialization() -> None:
    """Verify DecisionResult stores evaluation data correctly."""
    res = DecisionResult(
        decision_id="dec_01",
        event_id="evt_01",
        severity=DecisionSeverity.HIGH,
        action="escalate",
        reason="Test high priority",
        confidence=0.92,
        timestamp=1719876543.0,
        metadata={"camera_id": "cam_01"},
    )

    assert res.decision_id == "dec_01"
    assert res.event_id == "evt_01"
    assert res.severity == DecisionSeverity.HIGH
    assert res.action == "escalate"
    assert res.reason == "Test high priority"
    assert res.confidence == 0.92
    assert res.timestamp == 1719876543.0
    assert res.metadata == {"camera_id": "cam_01"}

    rep = repr(res)
    assert "dec_01" in rep
    assert "evt_01" in rep
    assert "high" in rep
    assert "escalate" in rep


# ==============================================================================
# 3. Test DecisionPolicy
# ==============================================================================
def test_decision_policy_thresholds() -> None:
    """Verify DecisionPolicy returns configured confidence thresholds and timing intervals."""
    policy = DecisionPolicy(
        confidence_thresholds={EventType.FIRE: 0.85},
        default_confidence_threshold=0.60,
        duplicate_suppression_window=30.0,
        cooldown_period=120.0,
    )

    assert policy.get_confidence_threshold(EventType.FIRE) == 0.85
    assert policy.get_confidence_threshold(EventType.SMOKE) == 0.60
    assert policy.duplicate_suppression_window == 30.0
    assert policy.cooldown_period == 120.0
    assert policy.metadata == {}


# ==============================================================================
# 4. Test BaseRule ABC
# ==============================================================================
def test_base_rule_abc_constraint() -> None:
    """Verify BaseRule cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseRule()  # type: ignore

    class BuggyRule(BaseRule):
        pass

    with pytest.raises(TypeError):
        BuggyRule()  # type: ignore


# ==============================================================================
# 5. Test Concrete Rules
# ==============================================================================
def test_confidence_threshold_rule() -> None:
    """Verify ConfidenceThresholdRule suppresses events below policy threshold."""
    rule = ConfidenceThresholdRule()
    policy = DecisionPolicy(default_confidence_threshold=0.70)
    event = Event(
        event_id="evt_01",
        event_type=EventType.FIRE,
        camera_id="cam_01",
        timestamp=time.time(),
        priority=EventPriority.CRITICAL,
        status=EventStatus.NEW,
        confidence=0.65,  # below 0.70
        description="Fire detected",
    )

    context: Dict[str, Any] = {"suppressed": False, "action": "monitor", "reason": ""}
    rule.evaluate(event, policy, context)

    assert context["suppressed"] is True
    assert context["action"] == "suppress"
    assert "below policy threshold" in context["reason"]


def test_duplicate_suppression_rule() -> None:
    """Verify DuplicateSuppressionRule identifies duplicates within suppression window."""
    rule = DuplicateSuppressionRule()
    policy = DecisionPolicy(duplicate_suppression_window=60.0)

    now = time.time()
    past_event = Event(
        event_id="evt_past",
        event_type=EventType.FIRE,
        camera_id="cam_01",
        timestamp=now - 45.0,  # 45 seconds ago (within 60s)
        priority=EventPriority.HIGH,
        status=EventStatus.NEW,
        confidence=0.80,
        description="Old smoke",
    )
    current_event = Event(
        event_id="evt_curr",
        event_type=EventType.FIRE,
        camera_id="cam_01",
        timestamp=now,
        priority=EventPriority.CRITICAL,
        status=EventStatus.NEW,
        confidence=0.85,
        description="New smoke",
    )

    context: Dict[str, Any] = {
        "suppressed": False,
        "action": "monitor",
        "reason": "",
        "history": [past_event],
    }

    rule.evaluate(current_event, policy, context)
    assert context["suppressed"] is True
    assert context["action"] == "suppress"
    assert "Duplicate event suppressed" in context["reason"]


def test_severity_calculation_rule() -> None:
    """Verify SeverityCalculationRule maps EventPriority correctly to DecisionSeverity."""
    rule = SeverityCalculationRule()
    policy = DecisionPolicy()
    event = Event(
        event_id="evt_01",
        event_type=EventType.FIRE,
        camera_id="cam_01",
        timestamp=time.time(),
        priority=EventPriority.CRITICAL,
        status=EventStatus.NEW,
        confidence=0.90,
        description="Critical event",
    )

    context: Dict[str, Any] = {}
    rule.evaluate(event, policy, context)
    assert context["severity"] == DecisionSeverity.CRITICAL


def test_action_determination_rule() -> None:
    """Verify ActionDeterminationRule handles cooldown, monitor, and escalation pacing."""
    rule = ActionDeterminationRule()
    policy = DecisionPolicy(cooldown_period=100.0)

    now = time.time()
    event = Event(
        event_id="evt_01",
        event_type=EventType.FIRE,
        camera_id="cam_01",
        timestamp=now,
        priority=EventPriority.CRITICAL,
        status=EventStatus.NEW,
        confidence=0.90,
        description="Fire incident",
    )

    # 1. Test standard escalation
    context_esc: Dict[str, Any] = {
        "suppressed": False,
        "severity": DecisionSeverity.CRITICAL,
        "last_escalation_time": 0.0,
    }
    rule.evaluate(event, policy, context_esc)
    assert context_esc["action"] == "escalate"

    # 2. Test cooldown suppression
    context_cool: Dict[str, Any] = {
        "suppressed": False,
        "severity": DecisionSeverity.CRITICAL,
        "last_escalation_time": now - 50.0,  # 50s ago (within 100s cooldown)
    }
    rule.evaluate(event, policy, context_cool)
    assert context_cool["action"] == "cooldown"
    assert "cooldown" in context_cool["reason"]


# ==============================================================================
# 6. Test DecisionEngine
# ==============================================================================
def test_decision_engine_evaluation_flow() -> None:
    """Verify DecisionEngine coordinates evaluation, tracking history, and returns valid DecisionResult."""
    engine = DecisionEngine(
        policy=DecisionPolicy(default_confidence_threshold=0.80, duplicate_suppression_window=30.0)
    )

    # 1. Event passes confidence threshold -> Escalates
    now = time.time()
    evt1 = Event(
        event_id="evt_pass",
        event_type=EventType.FIRE,
        camera_id="cam_01",
        timestamp=now,
        priority=EventPriority.CRITICAL,
        status=EventStatus.NEW,
        confidence=0.90,
        description="Active flame",
    )

    res1 = engine.evaluate_event(evt1)
    assert res1.event_id == "evt_pass"
    assert res1.severity == DecisionSeverity.CRITICAL
    assert res1.action == "escalate"
    assert engine.get_history() == [evt1]

    # 2. Event is duplicate of evt1 within 30s -> Suppressed
    evt2 = Event(
        event_id="evt_dup",
        event_type=EventType.FIRE,
        camera_id="cam_01",
        timestamp=now + 10.0,  # 10 seconds later
        priority=EventPriority.CRITICAL,
        status=EventStatus.NEW,
        confidence=0.90,
        description="Duplicate flame",
    )

    res2 = engine.evaluate_event(evt2)
    assert res2.event_id == "evt_dup"
    assert res2.action == "suppress"
    assert engine.get_history() == [evt1, evt2]

    # 3. Parameter validation
    with pytest.raises(DecisionError):
        engine.evaluate_event(None)  # type: ignore

    # 4. Engine clear
    engine.clear()
    assert len(engine.get_history()) == 0


def test_decision_engine_rule_failure_propagation() -> None:
    """Verify that if a rule fails, RuleExecutionError is raised."""
    class FailingRule(BaseRule):
        def evaluate(self, event: Event, policy: DecisionPolicy, context: Dict[str, Any]) -> None:
            raise ValueError("Injected rule failure")

    engine = DecisionEngine(rules=[FailingRule()])
    event = Event(
        event_id="evt_fail",
        event_type=EventType.FIRE,
        camera_id="cam_01",
        timestamp=time.time(),
        priority=EventPriority.CRITICAL,
        status=EventStatus.NEW,
        confidence=0.90,
        description="Error test",
    )

    with pytest.raises(RuleExecutionError):
        engine.evaluate_event(event)


def test_decision_engine_concurrency() -> None:
    """Verify that multiple threads can safely evaluate events on the same engine concurrently."""
    engine = DecisionEngine()
    num_threads = 10
    num_events_per_thread = 5

    def worker(thread_idx: int) -> List[DecisionResult]:
        results: List[DecisionResult] = []
        for i in range(num_events_per_thread):
            evt = Event(
                event_id=f"evt_t{thread_idx}_e{i}",
                event_type=EventType.FIRE,
                camera_id=f"cam_thread_{thread_idx}",
                timestamp=time.time(),
                priority=EventPriority.HIGH,
                status=EventStatus.NEW,
                confidence=0.95,
                description=f"Concurrent fire thread {thread_idx} event {i}",
            )
            results.append(engine.evaluate_event(evt))
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, idx) for idx in range(num_threads)]
        concurrent.futures.wait(futures)

    # Check all events successfully ran and are in history
    all_results: List[DecisionResult] = []
    for f in futures:
        all_results.extend(f.result())

    assert len(all_results) == num_threads * num_events_per_thread
    assert len(engine.get_history()) == num_threads * num_events_per_thread
