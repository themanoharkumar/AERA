"""AlertManager coordination layer for AERA.

This module defines the AlertManager class, coordinating alert generation,
channel dispatching, retry logic, and history recording.
"""

import logging
import threading
import time
import uuid
from typing import Dict, List, Optional

from src.alert.alert import Alert
from src.alert.channels import ConsoleNotifier
from src.alert.exceptions import AlertError
from src.alert.history import AlertHistory
from src.alert.notifier import BaseNotifier
from src.report.report import Report

logger = logging.getLogger(__name__)


class AlertManager:
    """Coordinates alert creation, notification delivery, retry handling, and history logs.

    Thread-safely manages registered channels and processed alerts.
    """

    def __init__(
        self,
        history: Optional[AlertHistory] = None,
        default_channel_name: str = "ConsoleNotifier",
    ) -> None:
        """Initialize the AlertManager.

        Args:
            history: Optional custom AlertHistory. Defaults to fresh AlertHistory.
            default_channel_name: Default channel name for dispatches if none is specified.
        """
        self.history = history if history is not None else AlertHistory()
        self.default_channel_name = default_channel_name

        self._channels: Dict[str, BaseNotifier] = {}
        self._alerts: Dict[str, Alert] = {}
        self._lock = threading.Lock()

        # Register default console notifier
        self.register_channel(ConsoleNotifier())

    def register_channel(self, notifier: BaseNotifier) -> None:
        """Register a new notification delivery channel.

        Args:
            notifier: Subclass of BaseNotifier.
        """
        if notifier is None:
            raise AlertError("Notifier channel cannot be None.")
        with self._lock:
            self._channels[notifier.name] = notifier
            logger.info("Registered notification channel: %s", notifier.name)

    def trigger_alert(
        self,
        report: Report,
        channel_name: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ) -> Alert:
        """Create and dispatch an alert from an Incident Report.

        Args:
            report: The Incident Report payload to notify.
            channel_name: The name of the channel to deliver to. Defaults to default_channel_name.
            max_retries: Maximum delivery retries on failure.
            retry_delay: Delay in seconds between retries.

        Returns:
            The created Alert object containing the final delivery status.

        Raises:
            AlertError: If delivery fails after all retries or validations fail.
        """
        if report is None:
            raise AlertError("Report cannot be None.")

        # Determine target channel
        target_name = channel_name if channel_name is not None else self.default_channel_name
        with self._lock:
            channel = self._channels.get(target_name)

        if not channel:
            raise AlertError(f"Notification channel '{target_name}' is not registered.")

        alert_id = str(uuid.uuid4())
        success = False
        retry_count = 0

        # Delivery retry loop
        while retry_count <= max_retries:
            try:
                success = channel.send_notification(report)
                if success:
                    break
            except Exception as e:
                logger.warning(
                    "Delivery attempt %d failed on channel %s for alert %s: %s",
                    retry_count,
                    target_name,
                    alert_id,
                    e,
                )

            retry_count += 1
            if retry_count <= max_retries:
                time.sleep(retry_delay)

        status = "success" if success else "failed"
        timestamp = time.time()

        # Record result in history
        self.history.record_delivery(
            alert_id=alert_id,
            timestamp=timestamp,
            channel=target_name,
            status=status,
            retry_count=max_retries if not success else max(0, retry_count),
        )

        # Extract severity from metadata or title
        severity = "UNKNOWN"
        if report.metadata and "severity" in report.metadata:
            severity = str(report.metadata["severity"])
        elif report.title and "-" in report.title:
            severity = report.title.split("-")[-1].strip()

        # Build Alert record
        alert = Alert(
            alert_id=alert_id,
            report_id=report.report_id,
            severity=severity,
            timestamp=timestamp,
            status=status,
            metadata={
                "channel": target_name,
                "retry_count": max_retries if not success else max(0, retry_count),
            },
        )

        with self._lock:
            self._alerts[alert_id] = alert

        if not success:
            raise AlertError(
                f"Alert delivery failed on channel '{target_name}' after {max_retries} retries."
            )

        return alert

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Retrieve a generated alert from cache.

        Args:
            alert_id: Unique alert identifier.

        Returns:
            The Alert object if cached, otherwise None.
        """
        with self._lock:
            return self._alerts.get(alert_id)

    def list_alerts(self) -> List[Alert]:
        """Get a copy list of all cached alerts.

        Returns:
            List of Alert objects.
        """
        with self._lock:
            return list(self._alerts.values())

    def clear(self) -> None:
        """Clear cached alerts and delivery histories."""
        with self._lock:
            self._alerts.clear()
            self.history.clear()
            logger.info("AlertManager alerts and history cleared.")
