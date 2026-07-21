"""Unit tests for the AERA Evidence Management System.

This module contains test cases verifying exception classes, immutable entity dataclasses,
EvidenceMetadata dict-conversions, LocalStorage layout structures, stateless validator checks,
and thread-safe orchestrations inside EvidenceManager.
"""

import time
import shutil
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, List
import pytest

from src.evidence import (
    BaseStorage,
    Evidence,
    EvidenceError,
    EvidenceManager,
    EvidenceMetadata,
    EvidenceValidator,
    LocalStorage,
    StorageError,
    ValidationError,
)


# ==============================================================================
# 1. Custom Exceptions & Immutability
# ==============================================================================
def test_exceptions_hierarchy() -> None:
    """Verify exceptions inherit from EvidenceError and carry correct messages."""
    assert issubclass(StorageError, EvidenceError)
    assert issubclass(ValidationError, EvidenceError)

    exc = ValidationError("Validation check failed")
    assert str(exc) == "Validation check failed"
    assert exc.message == "Validation check failed"


def test_evidence_immutability() -> None:
    """Verify that Evidence class instances are frozen and immutable."""
    evidence = Evidence(
        evidence_id="ev_001",
        event_id="evt_001",
        decision_id="dec_001",
        image_path="/path/image.jpg",
        video_path="/path/clip.mp4",
        timestamp=time.time(),
        metadata={"camera_id": "cam_001"},
    )

    assert evidence.evidence_id == "ev_001"
    with pytest.raises(AttributeError):
        evidence.evidence_id = "ev_002"  # type: ignore


# ==============================================================================
# 2. EvidenceMetadata Dict Conversions
# ==============================================================================
def test_evidence_metadata_conversions() -> None:
    """Verify EvidenceMetadata serialization and deserialization helpers."""
    original = EvidenceMetadata(
        camera_id="cam_abc",
        event_id="evt_abc",
        decision_id="dec_abc",
        timestamp=1719876543.0,
        detector_name="HeuristicFireModel",
        file_size=1024,
        resolution=(1920, 1080),
        custom_metadata={"confidence": 0.95},
    )

    data_dict = original.to_dict()
    assert data_dict["camera_id"] == "cam_abc"
    assert data_dict["file_size"] == 1024
    assert data_dict["resolution"] == (1920, 1080)

    # Reconstruct from dict
    reconstructed = EvidenceMetadata.from_dict(data_dict)
    assert reconstructed.camera_id == "cam_abc"
    assert reconstructed.resolution == (1920, 1080)
    assert reconstructed.custom_metadata == {"confidence": 0.95}

    # Reconstruct from partial dict
    partial = EvidenceMetadata.from_dict({"camera_id": "cam_2", "resolution": [640, 480]})
    assert partial.camera_id == "cam_2"
    assert partial.resolution == (640, 480)
    assert partial.event_id == ""


# ==============================================================================
# 3. BaseStorage ABC Constraints
# ==============================================================================
def test_base_storage_abc() -> None:
    """Verify BaseStorage cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseStorage()  # type: ignore


# ==============================================================================
# 4. LocalStorage Persistence
# ==============================================================================
def test_local_storage_lifecycle(tmp_path: Path) -> None:
    """Verify LocalStorage saves files, organizes directories, reads, and deletes."""
    storage = LocalStorage(root_dir=str(tmp_path))

    event_id = "event_test_01"
    timestamp = 1719876543.0  # 2024-07-02 UTC approximately
    image_bytes = b"fake-jpeg-data"
    video_bytes = b"fake-mp4-data"
    meta_dict = {"source": "unit_test"}

    # Save
    img_p, vid_p, meta_p = storage.save_evidence(
        event_id=event_id,
        timestamp=timestamp,
        image_data=image_bytes,
        video_data=video_bytes,
        metadata=meta_dict,
    )

    # Check paths exist and are structured by YYYY/MM/DD/event_id/
    assert img_p is not None
    assert vid_p is not None
    assert meta_p is not None

    path_obj = Path(img_p)
    assert path_obj.exists()
    assert path_obj.name == "image.jpg"
    assert path_obj.parent.name == event_id

    # Retrieve
    retrieved_meta = storage.retrieve_metadata(event_id, timestamp)
    assert retrieved_meta == {"source": "unit_test"}

    # Delete
    storage.delete_evidence(event_id, timestamp)
    assert not path_obj.parent.exists()


# ==============================================================================
# 5. EvidenceValidator Checks
# ==============================================================================
def test_evidence_validator_metadata() -> None:
    """Verify validator flags invalid metadata parameters."""
    validator = EvidenceValidator()

    # 1. Invalid required fields
    meta_bad = EvidenceMetadata(
        camera_id="",
        event_id="evt_01",
        decision_id="dec_01",
        timestamp=time.time(),
        detector_name="Detector",
        file_size=100,
        resolution=(640, 480),
        custom_metadata={},
    )
    with pytest.raises(ValidationError) as exc:
        validator.validate_metadata(meta_bad)
    assert "camera_id" in str(exc.value)

    # 2. Negative timestamps
    meta_bad_time = EvidenceMetadata(
        camera_id="cam_01",
        event_id="evt_01",
        decision_id="dec_01",
        timestamp=-10.0,
        detector_name="Detector",
        file_size=100,
        resolution=(640, 480),
        custom_metadata={},
    )
    with pytest.raises(ValidationError) as exc:
        validator.validate_metadata(meta_bad_time)
    assert "timestamp" in str(exc.value)


def test_evidence_validator_paths() -> None:
    """Verify validator flags corrupt or empty file paths and extension prefixes."""
    validator = EvidenceValidator()

    # 1. At least one path must exist
    with pytest.raises(ValidationError):
        validator.validate_paths(None, None)

    # 2. Invalid image extension
    with pytest.raises(ValidationError):
        validator.validate_paths("screenshot.gif", None)

    # 3. Invalid video extension
    with pytest.raises(ValidationError):
        validator.validate_paths(None, "video.mov")


def test_evidence_validator_duplicates() -> None:
    """Verify validator rejects duplicate events."""
    validator = EvidenceValidator()

    validator.register_event("evt_unique_1")
    validator.check_duplicate("evt_unique_2")  # should pass

    with pytest.raises(ValidationError):
        validator.check_duplicate("evt_unique_1")  # duplicate!

    validator.clear()
    validator.check_duplicate("evt_unique_1")  # should pass now


# ==============================================================================
# 6. EvidenceManager Coordination & Thread-safety
# ==============================================================================
def test_evidence_manager_e2e(tmp_path: Path) -> None:
    """Verify EvidenceManager coordinate validations, saves, list retrieval, and deletion."""
    storage = LocalStorage(root_dir=str(tmp_path))
    manager = EvidenceManager(storage=storage)

    meta = EvidenceMetadata(
        camera_id="cam_01",
        event_id="evt_e2e",
        decision_id="dec_e2e",
        timestamp=time.time(),
        detector_name="HeuristicFireModel",
        file_size=500,
        resolution=(1280, 720),
        custom_metadata={},
    )

    # 1. Successful creation
    evidence = manager.create_evidence(
        event_id="evt_e2e",
        decision_id="dec_e2e",
        metadata=meta,
        image_data=b"image-data-bytes",
    )

    assert evidence.event_id == "evt_e2e"
    assert evidence.decision_id == "dec_e2e"
    assert Path(evidence.image_path).exists()

    # 2. Retrieval checks
    assert manager.get_evidence("evt_e2e") == evidence
    assert manager.list_evidence() == [evidence]

    # 3. Duplicate rejection on manager layer
    with pytest.raises(ValidationError):
        manager.create_evidence(
            event_id="evt_e2e",
            decision_id="dec_e2e_2",
            metadata=meta,
        )

    # 4. Deletion checks
    manager.delete_evidence("evt_e2e", meta.timestamp)
    assert manager.get_evidence("evt_e2e") is None
    assert len(manager.list_evidence()) == 0


def test_evidence_manager_concurrency(tmp_path: Path) -> None:
    """Verify EvidenceManager handles concurrent creation requests thread-safely."""
    storage = LocalStorage(root_dir=str(tmp_path))
    manager = EvidenceManager(storage=storage)

    num_threads = 8
    num_events_per_thread = 5

    def worker(thread_idx: int) -> List[Evidence]:
        results: List[Evidence] = []
        for i in range(num_events_per_thread):
            event_id = f"evt_t{thread_idx}_e{i}"
            meta = EvidenceMetadata(
                camera_id=f"cam_{thread_idx}",
                event_id=event_id,
                decision_id=f"dec_t{thread_idx}_e{i}",
                timestamp=time.time(),
                detector_name="FireModel",
                file_size=200,
                resolution=(640, 480),
                custom_metadata={},
            )
            evidence = manager.create_evidence(
                event_id=event_id,
                decision_id=f"dec_t{thread_idx}_e{i}",
                metadata=meta,
                image_data=b"dummy-jpeg",
            )
            results.append(evidence)
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, idx) for idx in range(num_threads)]
        concurrent.futures.wait(futures)

    all_evidence = manager.list_evidence()
    assert len(all_evidence) == num_threads * num_events_per_thread

    # Clean files up
    manager.clear()
    assert len(manager.list_evidence()) == 0
