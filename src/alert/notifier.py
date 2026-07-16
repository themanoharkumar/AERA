"""Notification channel abstract definitions for the AERA Alert System.

This module defines the BaseNotifier abstract class, providing the standard interface
for delivering notifications from Incident Reports.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.report.report import Report


class BaseNotifier(ABC):
    """Abstract base class for emergency notification dispatch channels.

    Enables independent channels (e.g. Console, Email, SMS, Webhooks) to integrate
    without modifying AlertManager logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the identification name of this notification channel.

        Returns:
            The notifier channel name as string.
        """
        pass

    @abstractmethod
    def send_notification(self, report: Report, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send the formatted notification containing incident report details.

        Args:
            report: The Report object containing incident details.
            metadata: Optional dictionary with custom channel delivery parameters.

        Returns:
            True if the notification is successfully delivered, False otherwise.

        Raises:
            NotificationError: If validation or channel delivery operations fail.
        """
        pass

    @abstractmethod
    def validate_payload(self, report: Report) -> None:
        """Validate that the Report contains necessary parameters for dispatch.

        Args:
            report: The Report instance to check.

        Raises:
            NotificationError: If fields are corrupt, empty, or invalid.
        """
        pass
