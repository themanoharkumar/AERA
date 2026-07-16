"""Alert entity definitions for the AERA Alert System.

This module defines the Alert class representing an immutable alert delivery record.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Alert:
    """Represents a frozen, immutable record of a dispatched alert.

    Exposes status information and a delivery_status alias for specification compliance.
    """

    alert_id: str
    report_id: str
    severity: str
    timestamp: float
    status: str
    metadata: Dict[str, Any]

    @property
    def delivery_status(self) -> str:
        """Alias for the underlying status attribute, satisfying user specs."""
        return self.status
