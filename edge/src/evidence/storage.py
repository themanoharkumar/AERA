"""Evidence storage abstraction and implementations for AERA.

This module defines the BaseStorage interface and the LocalStorage implementation,
handling physical persistence and layout of incident evidence packages.
"""

from abc import ABC, abstractmethod
from datetime import datetime
import json
import logging
from pathlib import Path
import shutil
from typing import Any, Dict, Optional, Tuple

from src.evidence.exceptions import StorageError

logger = logging.getLogger(__name__)


class BaseStorage(ABC):
    """Abstract base class specifying the interface for evidence file storage.

    Decouples AERA components from underlying storage engines (e.g. Local disk,
    GCS, AWS S3, or Azure Blob storage).
    """

    @abstractmethod
    def save_evidence(
        self,
        event_id: str,
        timestamp: float,
        image_data: Optional[bytes] = None,
        video_data: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Optional[str], str]:
        """Save evidence files organized hierarchically by date and event_id.

        Args:
            event_id: Unique event identifier.
            timestamp: Epoch timestamp of the event.
            image_data: Optional raw bytes of the incident screenshot.
            video_data: Optional raw bytes of the video clip.
            metadata: Optional dictionary of serialized metadata.

        Returns:
            A tuple of (saved_image_path, saved_video_path, saved_metadata_path).

        Raises:
            StorageError: If file creation or directory setups fail.
        """
        pass

    @abstractmethod
    def delete_evidence(self, event_id: str, timestamp: float) -> None:
        """Delete all evidence files and container directory for an event.

        Args:
            event_id: Unique event identifier.
            timestamp: Epoch timestamp of the event.

        Raises:
            StorageError: If deletion fails.
        """
        pass

    @abstractmethod
    def retrieve_metadata(self, event_id: str, timestamp: float) -> Dict[str, Any]:
        """Retrieve serialized metadata for a stored event evidence package.

        Args:
            event_id: Unique event identifier.
            timestamp: Epoch timestamp of the event.

        Returns:
            A dictionary containing serialized metadata.

        Raises:
            StorageError: If retrieval fails.
        """
        pass


class LocalStorage(BaseStorage):
    """Local disk implementation of BaseStorage.

    Saves evidence files to a predictable local path:
    {root_dir}/YYYY/MM/DD/{event_id}/
    """

    def __init__(self, root_dir: str = "evidence_records") -> None:
        """Initialize the LocalStorage instance.

        Args:
            root_dir: Base directory path on local disk for all evidence storage.
        """
        self.root_path = Path(root_dir).resolve()

    def _get_event_directory(self, event_id: str, timestamp: float) -> Path:
        """Construct the absolute path to the event evidence directory.

        Format: root_path/YYYY/MM/DD/event_id/
        """
        dt = datetime.fromtimestamp(timestamp)
        year = f"{dt.year:04d}"
        month = f"{dt.month:02d}"
        day = f"{dt.day:02d}"
        return self.root_path / year / month / day / event_id

    def save_evidence(
        self,
        event_id: str,
        timestamp: float,
        image_data: Optional[bytes] = None,
        video_data: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Optional[str], str]:
        """Save evidence files to local disk under date-partitioned event directories."""
        if not event_id:
            raise StorageError("Event ID cannot be empty.")

        try:
            event_dir = self._get_event_directory(event_id, timestamp)
            event_dir.mkdir(parents=True, exist_ok=True)

            saved_image_path: Optional[str] = None
            saved_video_path: Optional[str] = None

            # Save screenshot
            if image_data is not None:
                img_file = event_dir / "image.jpg"
                img_file.write_bytes(image_data)
                saved_image_path = str(img_file.resolve().as_posix())

            # Save video clip
            if video_data is not None:
                video_file = event_dir / "clip.mp4"
                video_file.write_bytes(video_data)
                saved_video_path = str(video_file.resolve().as_posix())

            # Save metadata JSON file
            metadata_file = event_dir / "metadata.json"
            meta_dict = metadata if metadata is not None else {}
            metadata_file.write_text(json.dumps(meta_dict, indent=4), encoding="utf-8")
            saved_metadata_path = str(metadata_file.resolve().as_posix())

            logger.info("Saved local evidence for event %s to: %s", event_id, event_dir)
            return saved_image_path, saved_video_path, saved_metadata_path

        except Exception as e:
            logger.exception("Failed to write local storage files for event %s", event_id)
            raise StorageError(f"LocalStorage save failed for event {event_id}: {e}") from e

    def delete_evidence(self, event_id: str, timestamp: float) -> None:
        """Delete local directories and files associated with event evidence."""
        if not event_id:
            raise StorageError("Event ID cannot be empty.")

        try:
            event_dir = self._get_event_directory(event_id, timestamp)
            if event_dir.exists() and event_dir.is_dir():
                shutil.rmtree(event_dir)
                logger.info("Deleted local evidence directory: %s", event_dir)
            else:
                logger.warning("Evidence directory not found for deletion: %s", event_dir)
        except Exception as e:
            logger.exception("Failed to delete local evidence directory for event %s", event_id)
            raise StorageError(f"LocalStorage deletion failed for event {event_id}: {e}") from e

    def retrieve_metadata(self, event_id: str, timestamp: float) -> Dict[str, Any]:
        """Retrieve local metadata json file content."""
        if not event_id:
            raise StorageError("Event ID cannot be empty.")

        try:
            event_dir = self._get_event_directory(event_id, timestamp)
            metadata_file = event_dir / "metadata.json"
            if not metadata_file.exists():
                raise StorageError(f"Metadata file not found on disk for event {event_id}.")

            with open(metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            if isinstance(e, StorageError):
                raise
            logger.exception("Failed to read local metadata file for event %s", event_id)
            raise StorageError(f"LocalStorage retrieval failed for event {event_id}: {e}") from e
