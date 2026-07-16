"""EvidenceManager coordination layer for AERA.

This module defines the EvidenceManager class, which coordinates validation,
storage persistence, and CRUD lifecycles of emergency evidence packages.
"""

import logging
import threading
import uuid
from typing import Dict, List, Optional

from src.evidence.evidence import Evidence
from src.evidence.exceptions import EvidenceError
from src.evidence.metadata import EvidenceMetadata
from src.evidence.storage import BaseStorage, LocalStorage
from src.evidence.validator import EvidenceValidator

logger = logging.getLogger(__name__)


class EvidenceManager:
    """Coordinates evidence package creation, validation, storage, and lifecycle.

    Guarantees thread safety and metadata integrity while persisting incident proof files.
    """

    def __init__(
        self,
        storage: Optional[BaseStorage] = None,
        validator: Optional[EvidenceValidator] = None,
    ) -> None:
        """Initialize the EvidenceManager.

        Args:
            storage: Optional custom BaseStorage engine. Defaults to a LocalStorage engine.
            validator: Optional custom EvidenceValidator. Defaults to a fresh EvidenceValidator.
        """
        self.storage = storage if storage is not None else LocalStorage()
        self.validator = validator if validator is not None else EvidenceValidator()

        # Thread-safe in-memory cache of active Evidence records indexed by event_id
        self._evidence_records: Dict[str, Evidence] = {}
        self._lock = threading.Lock()

    def create_evidence(
        self,
        event_id: str,
        decision_id: str,
        metadata: EvidenceMetadata,
        image_data: Optional[bytes] = None,
        video_data: Optional[bytes] = None,
    ) -> Evidence:
        """Create, validate, and store a new Evidence package.

        Args:
            event_id: Unique event identifier.
            decision_id: Unique decision identifier.
            metadata: Structured EvidenceMetadata containing incident details.
            image_data: Optional raw bytes of screenshot file.
            video_data: Optional raw bytes of video clip file.

        Returns:
            The created immutable Evidence instance.

        Raises:
            EvidenceError: If validation checks fail or storage writes encounter errors.
        """
        if not event_id:
            raise EvidenceError("Event ID cannot be empty.")
        if not decision_id:
            raise EvidenceError("Decision ID cannot be empty.")
        if metadata is None:
            raise EvidenceError("Metadata cannot be None.")

        with self._lock:
            # 1. Enforce duplication validation
            self.validator.check_duplicate(event_id)

            # 2. Run metadata validation checks
            self.validator.validate_metadata(metadata)

            # 3. Run path syntax formatting check on expected suffixes
            image_suffix = "image.jpg" if image_data is not None else None
            video_suffix = "clip.mp4" if video_data is not None else None
            self.validator.validate_paths(image_suffix, video_suffix)

            # 4. Save raw file buffers using configured storage provider
            img_path, vid_path, _ = self.storage.save_evidence(
                event_id=event_id,
                timestamp=metadata.timestamp,
                image_data=image_data,
                video_data=video_data,
                metadata=metadata.to_dict(),
            )

            # 5. Build final immutable Evidence object
            evidence_id = str(uuid.uuid4())
            evidence = Evidence(
                evidence_id=evidence_id,
                event_id=event_id,
                decision_id=decision_id,
                image_path=img_path or "",
                video_path=vid_path or "",
                timestamp=metadata.timestamp,
                metadata=metadata.to_dict(),
            )

            # 6. Prevent future duplicate entries and update in-memory caches
            self.validator.register_event(event_id)
            self._evidence_records[event_id] = evidence

            logger.info("Successfully created evidence package %s for event %s", evidence_id, event_id)
            return evidence

    def get_evidence(self, event_id: str) -> Optional[Evidence]:
        """Retrieve an Evidence package by event_id.

        Args:
            event_id: Unique event identifier.

        Returns:
            The cached Evidence instance, or None if not found.
        """
        with self._lock:
            return self._evidence_records.get(event_id)

    def list_evidence(self) -> List[Evidence]:
        """Get a list of all active Evidence packages.

        Returns:
            A list of cached Evidence objects.
        """
        with self._lock:
            return list(self._evidence_records.values())

    def delete_evidence(self, event_id: str, timestamp: float) -> None:
        """Delete evidence files from storage and remove it from manager cache.

        Args:
            event_id: Unique event identifier.
            timestamp: Epoch timestamp of the event.

        Raises:
            EvidenceError: If deletion fails.
        """
        if not event_id:
            raise EvidenceError("Event ID cannot be empty.")

        with self._lock:
            # Delete physical storage files
            self.storage.delete_evidence(event_id, timestamp)

            # Remove from cached registries
            if event_id in self._evidence_records:
                del self._evidence_records[event_id]

            logger.info("Successfully removed evidence files for event %s", event_id)

    def clear(self) -> None:
        """Clear all cached records, duplicate check registries, and stored files."""
        with self._lock:
            # We clear physical files for all cached event entries
            for event_id, evidence in list(self._evidence_records.items()):
                try:
                    self.storage.delete_evidence(event_id, evidence.timestamp)
                except Exception:
                    logger.warning("Failed to clean storage path during clear for event %s", event_id)

            self._evidence_records.clear()
            self.validator.clear()
            logger.info("EvidenceManager records and validator cleared.")
