"""Report entity definitions for the AERA Report Engine.

This module defines the Report class representing an immutable incident report package.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Report:
    """Represents a frozen, immutable human-readable incident report.

    Contains identifiers, titles, human-readable summary, and structured metadata.
    """

    report_id: str
    event_id: str
    decision_id: str
    evidence_id: str
    title: str
    summary: str
    timestamp: float
    metadata: Dict[str, Any]
