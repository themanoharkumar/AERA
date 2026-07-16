"""Evidence entity definitions for the AERA Evidence Management System.

This module defines the Evidence class representing an immutable evidence package
containing screenshots, video clips, and metadata references of verified incidents.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.evidence.metadata import EvidenceMetadata


@dataclass(frozen=True)
class Evidence:
    """Represents a frozen package of preserved evidence for validated incidents.

    Every instance of Evidence is immutable and contains paths to physical files
    and dynamic metadata describing the context of the incident.
    """

    evidence_id: str
    event_id: str
    decision_id: str
    image_path: str
    video_path: str
    timestamp: float
    metadata: Dict[str, Any]
