"""Unit tests for the AERA Event Management System.

This module contains test cases for exceptions, enums, Event entity,
and EventManager, including verification of validations, thread-safety, and query filters.
"""

import time
import concurrent.futures
from typing import List
import pytest

from src.event import (
    Event,
    EventManager,
    EventType,
    EventPriority,
    EventStatus,
    EventError,
    InvalidEventError,
    DuplicateEventError,
    EventNotFoundError,
    EventValidationError,
)


# ==============================================================================
# 1. Test Custom Exceptions
# ==============================================================================
def test_exceptions_hierarchy() -> None:
    """Verify exceptions inherit from EventError and support custom messages."""
    assert issubclass(InvalidEventError, EventError)
    assert issubclass(DuplicateEventError, EventError)
    assert issubclass(EventNotFoundError, EventError)
    assert issubclass(EventValidationError, EventError)

    exc = InvalidEventError("Custom invalid event")
    assert str(exc) == "Custom invalid event"
    assert exc.message == "Custom invalid event"


# ==============================================================================
# 2. Test Enums
# ==============================================================================
def test_enums_values() -> None:
    """Verify enums are string-based and contain correct values."""
    assert EventType.FIRE == "FIRE"
    assert EventPriority.CRITICAL == "CRITICAL"
    assert EventStatus.NEW == "NEW"

    # Enums should be instances of str for easy comparison/serialization
    assert isinstance(EventType.FIRE, str)
    assert isinstance(EventPriority.HIGH, str)
    assert isinstance(EventStatus.RESOLVED, str)


# ==============================================================================
# 3. Test Event Entity
# ==============================================================================
def test_event_entity_initialization() -> None:
    """Verify lightweight Event class initializes with correct values and defaults."""
    metadata = {"temp_celsius": 45.5}
    event = Event(
        event_id="evt_01",
        event_type=EventType.FIRE,
        camera_id="cam_01",
        timestamp=1719876543.21,
        priority=EventPriority.CRITICAL,
        status=EventStatus.NEW,
        confidence=0.98,
        description="Fire detected in room A",
        metadata=metadata,
    )

    assert event.event_id == "evt_01"
    assert event.event_type == EventType.FIRE
    assert event.camera_id == "cam_01"
    assert event.timestamp == 1719876543.21
    assert event.priority == EventPriority.CRITICAL
    assert event.status == EventStatus.NEW
    assert event.confidence == 0.98
    assert event.description == "Fire detected in room A"
    assert event.metadata == metadata

    # Check repr
    rep = repr(event)
    assert "evt_01" in rep
    assert "FIRE" in rep
    assert "CRITICAL" in rep
    assert "0.98" in rep


# ==============================================================================
# 4. Test EventManager - Creation and Registration
# ==============================================================================
def test_manager_creation_and_registration() -> None:
    """Verify EventManager correctly creates and registers events."""
    manager = EventManager()

    # Create event
    event = manager.create_event(
        event_type=EventType.FIRE,
        camera_id="cam_01",
        description="Fire detected",
        confidence=0.85,
        priority=EventPriority.HIGH,
    )

    assert event.event_id is not None
    assert event.event_type == EventType.FIRE
    assert event.camera_id == "cam_01"
    assert event.confidence == 0.85
    assert event.priority == EventPriority.HIGH
    assert event.status == EventStatus.NEW
    assert event.timestamp > 0.0

    # Test registration of custom event object
    custom_event = Event(
        event_id="custom_evt",
        event_type=EventType.SMOKE,
        camera_id="cam_02",
        timestamp=time.time(),
        priority=EventPriority.MEDIUM,
        status=EventStatus.NEW,
        confidence=0.70,
        description="Smoke rising",
    )
    manager.register_event(custom_event)
    assert manager.get_event("custom_evt") is custom_event

    # Duplicate registration fails
    with pytest.raises(DuplicateEventError):
        manager.register_event(custom_event)


# ==============================================================================
# 5. Test EventManager - Validations
# ==============================================================================
def test_manager_validations() -> None:
    """Verify EventManager validates event fields properly."""
    manager = EventManager()

    # Empty camera ID
    with pytest.raises(EventValidationError):
        manager.create_event(
            event_type=EventType.FIRE,
            camera_id="",
            description="Fire",
            confidence=0.8,
        )

    # Invalid confidence (above 1.0)
    with pytest.raises(EventValidationError):
        manager.create_event(
            event_type=EventType.FIRE,
            camera_id="cam_01",
            description="Fire",
            confidence=1.1,
        )

    # Invalid confidence (below 0.0)
    with pytest.raises(EventValidationError):
        manager.create_event(
            event_type=EventType.FIRE,
            camera_id="cam_01",
            description="Fire",
            confidence=-0.1,
        )

    # Invalid confidence (non-number)
    with pytest.raises(EventValidationError):
        manager.create_event(
            event_type=EventType.FIRE,
            camera_id="cam_01",
            description="Fire",
            confidence="high",  # type: ignore
        )

    # Invalid event type
    with pytest.raises(EventValidationError):
        manager.create_event(
            event_type="INVALID_TYPE",
            camera_id="cam_01",
            description="Fire",
            confidence=0.8,
        )


# ==============================================================================
# 6. Test EventManager - Updates
# ==============================================================================
def test_manager_updates() -> None:
    """Verify EventManager updates mutable fields and rejects immutable field updates."""
    manager = EventManager()
    event = manager.create_event(
        event_type=EventType.FALL,
        camera_id="cam_01",
        description="Fall detected",
        confidence=0.9,
        priority=EventPriority.LOW,
    )

    # Update mutable fields
    manager.update_event(
        event.event_id,
        priority=EventPriority.HIGH,
        status=EventStatus.PROCESSING,
        confidence=0.95,
        description="Fall verified and active",
        metadata={"responder": "John"},
    )

    updated = manager.get_event(event.event_id)
    assert updated.priority == EventPriority.HIGH
    assert updated.status == EventStatus.PROCESSING
    assert updated.confidence == 0.95
    assert updated.description == "Fall verified and active"
    assert updated.metadata == {"responder": "John"}

    # Direct helper update methods
    manager.update_status(event.event_id, EventStatus.RESOLVED)
    manager.update_priority(event.event_id, EventPriority.CRITICAL)
    assert updated.status == EventStatus.RESOLVED
    assert updated.priority == EventPriority.CRITICAL

    # Test update validation (invalid confidence)
    with pytest.raises(EventValidationError):
        manager.update_event(event.event_id, confidence=2.5)

    # Immutable fields cannot be updated
    with pytest.raises(EventValidationError):
        manager.update_event(event.event_id, event_id="new_id")

    with pytest.raises(EventValidationError):
        manager.update_event(event.event_id, event_type=EventType.VIOLENCE)

    with pytest.raises(EventValidationError):
        manager.update_event(event.event_id, camera_id="cam_new")

    with pytest.raises(EventValidationError):
        manager.update_event(event.event_id, timestamp=123.45)


# ==============================================================================
# 7. Test EventManager - Retrieval, Listing, and Deletion
# ==============================================================================
def test_manager_retrieval_and_deletion() -> None:
    """Verify EventManager retrieves, lists, and deletes events correctly."""
    manager = EventManager()

    # Get non-existent
    with pytest.raises(EventNotFoundError):
        manager.get_event("non_existent")

    # Delete non-existent
    with pytest.raises(EventNotFoundError):
        manager.delete_event("non_existent")

    # Create several events with custom timestamps for sorting verification
    evt1 = manager.create_event(
        event_type=EventType.FIRE, camera_id="cam_01", description="evt1", confidence=0.8, timestamp=100.0
    )
    evt2 = manager.create_event(
        event_type=EventType.SMOKE, camera_id="cam_02", description="evt2", confidence=0.7, timestamp=200.0
    )
    evt3 = manager.create_event(
        event_type=EventType.FALL, camera_id="cam_03", description="evt3", confidence=0.9, timestamp=150.0
    )

    # List events (should be sorted by timestamp descending: evt2 (200), evt3 (150), evt1 (100))
    lst = manager.list_events()
    assert len(lst) == 3
    assert lst[0].event_id == evt2.event_id
    assert lst[1].event_id == evt3.event_id
    assert lst[2].event_id == evt1.event_id

    # Delete one
    manager.delete_event(evt3.event_id)
    with pytest.raises(EventNotFoundError):
        manager.get_event(evt3.event_id)
    assert len(manager.list_events()) == 2

    # Clear
    manager.clear_events()
    assert len(manager.list_events()) == 0


# ==============================================================================
# 8. Test EventManager - Search & Filtering
# ==============================================================================
def test_manager_search_filtering() -> None:
    """Verify EventManager search filtering criteria work perfectly."""
    manager = EventManager()

    # Register sample set
    manager.create_event("FIRE", "cam_01", "F1", 0.95, "CRITICAL", timestamp=100.0)
    manager.create_event("SMOKE", "cam_01", "S1", 0.70, "HIGH", timestamp=110.0)
    manager.create_event("FALL", "cam_02", "FA1", 0.85, "MEDIUM", timestamp=120.0)
    manager.create_event("FIRE", "cam_03", "F2", 0.50, "LOW", timestamp=130.0)

    # No filters returns all, sorted desc
    assert len(manager.search_events()) == 4

    # Filter by event_type (single string)
    res = manager.search_events({"event_type": "FIRE"})
    assert len(res) == 2
    assert res[0].description == "F2"
    assert res[1].description == "F1"

    # Filter by event_type (list/tuple)
    res = manager.search_events({"event_type": [EventType.FIRE, EventType.SMOKE]})
    assert len(res) == 3

    # Filter by camera_id
    res = manager.search_events({"camera_id": "cam_01"})
    assert len(res) == 2

    # Filter by priority
    res = manager.search_events({"priority": EventPriority.MEDIUM})
    assert len(res) == 1
    assert res[0].event_type == EventType.FALL

    # Filter by status
    res = manager.search_events({"status": EventStatus.NEW})
    assert len(res) == 4

    # Filter by min_confidence
    res = manager.search_events({"min_confidence": 0.80})
    assert len(res) == 2  # 0.95, 0.85

    # Filter by timestamp range
    res = manager.search_events({"start_time": 105.0, "end_time": 125.0})
    assert len(res) == 2  # S1 (110) and FA1 (120)


# ==============================================================================
# 9. Test EventManager - Thread Safety
# ==============================================================================
def test_manager_thread_safety() -> None:
    """Verify EventManager is thread-safe under concurrent registrations."""
    manager = EventManager()
    num_threads = 10
    events_per_thread = 50

    def worker(thread_idx: int) -> List[str]:
        event_ids = []
        for i in range(events_per_thread):
            evt = manager.create_event(
                event_type=EventType.INTRUSION,
                camera_id=f"cam_{thread_idx}",
                description=f"Thread {thread_idx} event {i}",
                confidence=0.85,
            )
            event_ids.append(evt.event_id)
        return event_ids

    # Run concurrently using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, idx) for idx in range(num_threads)]
        concurrent.futures.wait(futures)

    # Assert total registered events equals num_threads * events_per_thread
    all_events = manager.list_events()
    assert len(all_events) == num_threads * events_per_thread

    # Check for correct data partitions
    cam_ids = [e.camera_id for e in all_events]
    for idx in range(num_threads):
        assert cam_ids.count(f"cam_{idx}") == events_per_thread
