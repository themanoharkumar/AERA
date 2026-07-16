"""Evidence metadata models for the AERA Evidence Management System.

This module defines the EvidenceMetadata class containing contextual descriptors
for stored emergency incident evidence files.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class EvidenceMetadata:
    """Represents standardized metadata details of preserved evidence files."""

    camera_id: str
    event_id: str
    decision_id: str
    timestamp: float
    detector_name: str
    file_size: int
    resolution: Tuple[int, int]
    custom_metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the metadata fields to a standard dictionary.

        Returns:
            A dictionary containing all evidence metadata properties.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceMetadata":
        """Reconstruct EvidenceMetadata from a serialized dictionary.

        Args:
            data: The source dictionary.

        Returns:
            A new EvidenceMetadata instance.
        """
        resolution_data = data.get("resolution", (0, 0))
        if isinstance(resolution_data, (list, tuple)) and len(resolution_data) >= 2:
            resolution = (int(resolution_data[0]), int(resolution_data[1]))
        else:
            resolution = (0, 0)

        return cls(
            camera_id=str(data.get("camera_id", "")),
            event_id=str(data.get("event_id", "")),
            decision_id=str(data.get("decision_id", "")),
            timestamp=float(data.get("timestamp", 0.0)),
            detector_name=str(data.get("detector_name", "")),
            file_size=int(data.get("file_size", 0)),
            resolution=resolution,
            custom_metadata=dict(data.get("custom_metadata", {})),
        )
