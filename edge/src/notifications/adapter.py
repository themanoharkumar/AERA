"""Notification channel adapter bridging AlertManager to NotificationManager."""

import logging
import os
from typing import Any, Dict, Optional

from src.alert.notifier import BaseNotifier as AlertBaseNotifier
from src.notifications.manager import NotificationManager
from src.notifications.models import NotificationAttachment, NotificationMessage
from src.report.report import Report

logger = logging.getLogger(__name__)


class TelegramNotifierAdapter(AlertBaseNotifier):
    """Adapter bridging AlertManager reports to the new NotificationManager subsystem."""

    def __init__(
        self,
        notification_manager: NotificationManager,
        recipient: str,
        coordinator_evidence_manager: Optional[Any] = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            notification_manager: Configured NotificationManager instance.
            recipient: Telegram Chat identifier.
            coordinator_evidence_manager: Optional EvidenceManager instance.
        """
        self._notification_manager = notification_manager
        self._recipient = recipient
        self._evidence_manager = coordinator_evidence_manager

    @property
    def name(self) -> str:
        """Return the identification name of this alert channel."""
        return "TelegramNotifier"

    def validate_payload(self, report: Report) -> None:
        """Validate report payload fields.

        Args:
            report: The Report payload.
        """
        if not report:
            raise ValueError("Report payload cannot be None.")
        if not report.report_id:
            raise ValueError("Report ID is missing.")

    def send_notification(self, report: Report, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Convert Report details and dispatch to NotificationManager.

        Args:
            report: The Report object to deliver.
            metadata: Custom delivery parameters.

        Returns:
            True if delivery succeeded, False otherwise.
        """
        self.validate_payload(report)

        photo_path: Optional[str] = None
        attachments = []

        # 1. Resolve photo path using coordinator's EvidenceManager
        if self._evidence_manager:
            try:
                evidence = self._evidence_manager.get_evidence(report.event_id)
                if evidence and evidence.image_path and os.path.exists(evidence.image_path):
                    photo_path = evidence.image_path
                    attachments.append(
                        NotificationAttachment(
                            file_path=photo_path,
                            content_type="image/jpeg",
                            filename=os.path.basename(photo_path),
                        )
                    )
            except Exception as e:
                logger.warning("TelegramNotifierAdapter: Failed to resolve evidence path: %s", e)

        # 2. Write report summary to disk (for sendDocument document attachment)
        report_path: Optional[str] = None
        if report.summary:
            try:
                report_dir = "storage/reports"
                os.makedirs(report_dir, exist_ok=True)
                report_path = f"{report_dir}/{report.report_id}.md"
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report.summary)
            except Exception as e:
                logger.warning("TelegramNotifierAdapter: Failed to write report file to disk: %s", e)

        # 3. Format incident details
        urgency = report.metadata.get("urgency", "MEDIUM")

        msg_metadata = {
            "emergency_type": report.title.replace("AERA Emergency Incident Report - ", ""),
            "severity": report.metadata.get("severity", urgency),
            "confidence": report.metadata.get("confidence", "N/A"),
            "camera": report.metadata.get("camera_id", "Unknown"),
            "event_id": report.event_id,
            "report_path": report_path,
        }

        message = NotificationMessage(
            recipient=self._recipient,
            subject=report.title,
            body=report.operator_summary or report.summary,
            urgency=urgency,
            attachments=attachments,
            metadata=msg_metadata,
        )

        # 4. Route notification
        res = self._notification_manager.route_notification("TelegramNotifier", message)
        return res.success
