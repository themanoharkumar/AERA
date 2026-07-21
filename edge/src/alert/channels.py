"""Notification channel implementations for AERA.

This module defines the concrete ConsoleNotifier class delivering incident report alerts
to logging handlers and stdout.
"""

import logging
from typing import Any, Dict, Optional

from src.alert.exceptions import NotificationError
from src.alert.notifier import BaseNotifier
from src.report.report import Report

logger = logging.getLogger(__name__)


class ConsoleNotifier(BaseNotifier):
    """Concrete notification channel executing console log output deliveries."""

    @property
    def name(self) -> str:
        """Return the identification name of the channel.

        Returns:
            String identifier: 'ConsoleNotifier'.
        """
        return "ConsoleNotifier"

    def validate_payload(self, report: Report) -> None:
        """Validate that the Report contains necessary parameters for console output."""
        if report is None:
            raise NotificationError("Report payload cannot be None.")

        if not report.report_id:
            raise NotificationError("Validation failed: 'report_id' is missing.")
        if not report.summary:
            raise NotificationError("Validation failed: Report 'summary' text is empty.")

    def send_notification(self, report: Report, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Deliver formatted incident report summary outputs directly to console streams."""
        self.validate_payload(report)

        try:
            logger.info(
                "\n--- CONSOLE ALERT DISPATCH ---\n%s\n------------------------------",
                report.summary,
            )
            return True
        except Exception as e:
            logger.exception("Failed to dispatch alert to console.")
            raise NotificationError(f"Console delivery failed: {e}") from e
