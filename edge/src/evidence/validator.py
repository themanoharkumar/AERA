"""Evidence validator implementation for AERA.

This module defines the EvidenceValidator class, which validates evidence objects
and metadata configurations independently of the physical storage engine.
"""

import logging
from typing import Any, Dict, Optional, Set

from src.evidence.exceptions import ValidationError
from src.evidence.metadata import EvidenceMetadata

logger = logging.getLogger(__name__)


class EvidenceValidator:
    """Performs validation checks on evidence metadata, paths, and duplication states."""

    def __init__(self) -> None:
        """Initialize the EvidenceValidator with an empty duplicate checking set."""
        self._processed_event_ids: Set[str] = set()

    def validate_metadata(self, metadata: EvidenceMetadata) -> None:
        """Validate an EvidenceMetadata instance.

        Checks that all required fields are present, populated, and hold valid values.

        Args:
            metadata: The EvidenceMetadata instance to validate.

        Raises:
            ValidationError: If metadata fields are invalid or missing.
        """
        if metadata is None:
            raise ValidationError("Metadata cannot be None.")

        # Required fields check
        if not metadata.camera_id:
            raise ValidationError("Validation failed: 'camera_id' must be populated.")
        if not metadata.event_id:
            raise ValidationError("Validation failed: 'event_id' must be populated.")
        if not metadata.decision_id:
            raise ValidationError("Validation failed: 'decision_id' must be populated.")
        if not metadata.detector_name:
            raise ValidationError("Validation failed: 'detector_name' must be populated.")

        # Numeric ranges validation
        if metadata.timestamp <= 0.0:
            raise ValidationError(f"Validation failed: 'timestamp' ({metadata.timestamp}) must be positive.")
        if metadata.file_size < 0:
            raise ValidationError(f"Validation failed: 'file_size' ({metadata.file_size}) cannot be negative.")

        # Resolution validation
        width, height = metadata.resolution
        if width < 0 or height < 0:
            raise ValidationError(f"Validation failed: Resolution dimensions ({width}x{height}) cannot be negative.")

    def validate_paths(self, image_path: Optional[str], video_path: Optional[str]) -> None:
        """Validate evidence file paths and format configurations.

        Verifies that at least one file path is provided and that paths end with
        expected incident file extensions.

        Args:
            image_path: Optional path to the screenshot.
            video_path: Optional path to the video clip.

        Raises:
            ValidationError: If paths are corrupt, missing, or have invalid formats.
        """
        if not image_path and not video_path:
            raise ValidationError("Validation failed: Evidence must contain at least an image_path or a video_path.")

        if image_path:
            path_lower = image_path.lower()
            if not any(path_lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png")):
                raise ValidationError(f"Validation failed: Image path '{image_path}' has invalid extension.")

        if video_path:
            path_lower = video_path.lower()
            if not any(path_lower.endswith(ext) for ext in (".mp4", ".avi", ".mkv")):
                raise ValidationError(f"Validation failed: Video path '{video_path}' has invalid extension.")

    def check_duplicate(self, event_id: str) -> None:
        """Verify the event_id has not already been processed.

        Args:
            event_id: The event identifier to check.

        Raises:
            ValidationError: If the event_id has already been validated.
        """
        if not event_id:
            raise ValidationError("Validation failed: Event ID cannot be empty.")

        if event_id in self._processed_event_ids:
            raise ValidationError(f"Validation failed: Duplicate evidence rejected for event '{event_id}'.")

    def register_event(self, event_id: str) -> None:
        """Register a validated event_id to prevent duplicates in future checks.

        Args:
            event_id: The event identifier to register.
        """
        if event_id:
            self._processed_event_ids.add(event_id)

    def clear(self) -> None:
        """Clear all registered event_id history."""
        self._processed_event_ids.clear()
