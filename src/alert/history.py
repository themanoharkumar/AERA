"""Alert delivery history tracker for AERA.

This module defines the HistoryRecord and AlertHistory classes, managing delivery timestamps,
retries, and status history logs thread-safely.
"""

from dataclasses import dataclass
import threading
from typing import Dict, List


@dataclass(frozen=True)
class HistoryRecord:
    """Represents a single alert delivery log entry."""

    delivery_timestamp: float
    notification_channel: str
    delivery_status: str
    retry_count: int


class AlertHistory:
    """Manages history tracking of dispatched alerts thread-safely.

    Maintains in-memory lists of history records mapping alert_ids to their delivery logs.
    """

    def __init__(self) -> None:
        """Initialize the AlertHistory tracker."""
        self._records: Dict[str, List[HistoryRecord]] = {}
        self._lock = threading.Lock()

    def record_delivery(
        self,
        alert_id: str,
        timestamp: float,
        channel: str,
        status: str,
        retry_count: int,
    ) -> None:
        """Record a delivery event.

        Args:
            alert_id: Unique alert identifier.
            timestamp: Epoch delivery timestamp.
            channel: Notification channel name.
            status: Delivery status (e.g. success or failure status).
            retry_count: The retry count value.
        """
        record = HistoryRecord(
            delivery_timestamp=timestamp,
            notification_channel=channel,
            delivery_status=status,
            retry_count=retry_count,
        )

        with self._lock:
            if alert_id not in self._records:
                self._records[alert_id] = []
            self._records[alert_id].append(record)

    def get_history(self, alert_id: str) -> List[HistoryRecord]:
        """Retrieve delivery history records for a specific alert.

        Args:
            alert_id: Unique alert identifier.

        Returns:
            A list of HistoryRecord logs.
        """
        with self._lock:
            return list(self._records.get(alert_id, []))

    def clear(self) -> None:
        """Clear all stored history logs."""
        with self._lock:
            self._records.clear()
