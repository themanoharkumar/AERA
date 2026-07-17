"""Telegram notifier channel integration for AERA."""

import logging
import time
from typing import Optional

from src.notifications.base import BaseNotifier
from src.notifications.client import TelegramClient, mask_secret
from src.notifications.exceptions import NotificationConfigError, NotificationValidationError
from src.notifications.models import (
    NotificationConfig,
    NotificationDeliveryStatus,
    NotificationMessage,
    NotificationResult,
)

logger = logging.getLogger(__name__)


def escape_markdown(text: str) -> str:
    """Escape special characters to prevent Telegram Markdown parsing syntax errors.

    Args:
        text: String content.

    Returns:
        Escaped string.
    """
    if not text:
        return ""
    str_val = str(text)
    # Standard MarkdownV1 characters: \ * _ ` [
    # Replace backslash first, then escape others
    return (
        str_val.replace("\\", "\\\\")
        .replace("*", "\\*")
        .replace("_", "\\_")
        .replace("`", "\\`")
        .replace("[", "\\[")
    )


class TelegramNotifier(BaseNotifier):
    """Production-grade Telegram notification channel adapter.

    Coordinates message formatting, connection retries, and document uploads.
    """

    def __init__(self, config: NotificationConfig) -> None:
        """Initialize the Telegram channel with configuration.

        Args:
            config: A NotificationConfig parameter payload.
        """
        self._config = config
        self._client = TelegramClient(
            bot_token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            timeout=config.timeout,
        )

    @property
    def name(self) -> str:
        """Return the notifier channel identity."""
        return "TelegramNotifier"

    def format_message(self, message: NotificationMessage) -> str:
        """Format the NotificationMessage into standard emergency Markdown.

        Args:
            message: The NotificationMessage content description.

        Returns:
            A formatted Markdown string.
        """
        meta = message.metadata
        
        # Pull parameters with safe fallbacks and escape them to prevent markdown parsing errors
        emergency_type = escape_markdown(meta.get("emergency_type", message.subject.upper()))
        severity = escape_markdown(meta.get("severity", message.urgency.upper()))
        confidence = escape_markdown(meta.get("confidence", "N/A"))
        camera = escape_markdown(meta.get("camera", "Unknown Source"))
        time_str = escape_markdown(meta.get("time", time.strftime("%Y-%m-%d %H:%M:%S")))
        event_id = escape_markdown(meta.get("event_id", "N/A"))
        decision = escape_markdown(meta.get("decision", "Immediate Response Required"))
        
        has_evidence = len(message.attachments) > 0
        has_report = "report_path" in meta and meta["report_path"]
        
        evidence_status = "Captured" if has_evidence else "Not Available"
        report_status = "Generated" if has_report else "Not Available"

        body_text = (
            f"*🚨 AERA EMERGENCY ALERT*\n\n"
            f"*Emergency*\n{emergency_type}\n\n"
            f"*Severity*\n{severity}\n\n"
            f"*Confidence*\n{confidence}\n\n"
            f"*Camera*\n{camera}\n\n"
            f"*Time*\n{time_str}\n\n"
            f"*Event ID*\n`{event_id}`\n\n"
            f"*Decision*\n{decision}\n\n"
            f"*Evidence*\n{evidence_status}\n\n"
            f"*Report*\n{report_status}\n\n"
            f"*System*\n`AERA v0.9`"
        )
        return body_text

    def validate(self, message: NotificationMessage) -> None:
        """Verify parameters of the message payload and configuration.

        Args:
            message: The NotificationMessage payload to validate.

        Raises:
            NotificationValidationError: If structural checks fail.
            NotificationConfigError: If connection configurations are missing.
        """
        # 1. Check configuration
        if not self._config.telegram_bot_token:
            raise NotificationConfigError("Telegram bot token is not configured.")
        if not self._config.telegram_chat_id:
            raise NotificationConfigError("Telegram chat identifier is not configured.")

        # 2. Check message properties
        if not message.recipient:
            raise NotificationValidationError("Recipient target identifier is missing.")
        if not message.body and not message.subject:
            raise NotificationValidationError("Notification message body/subject cannot be empty.")

        # 3. Check attachments properties
        for att in message.attachments:
            if not att.file_path:
                raise NotificationValidationError("Attachment file path cannot be empty.")
            if not att.content_type:
                raise NotificationValidationError("Attachment content type cannot be empty.")

    def send(self, message: NotificationMessage) -> NotificationResult:
        """Send the formatted emergency message via Telegram Bot API.

        Integrates retry logic with exponential backoff and photo uploads.

        Args:
            message: The NotificationMessage content description.

        Returns:
            A NotificationResult indicating delivery outcome.
        """
        start_time = time.time()
        
        # 1. Validate credentials and message payloads
        try:
            self.validate(message)
        except Exception as validation_err:
            logger.error("TelegramNotifier validation failed: %s", validation_err)
            return NotificationResult(
                success=False,
                status=NotificationDeliveryStatus.FAILED,
                channel=self.name,
                timestamp=time.time(),
                latency=time.time() - start_time,
                error_message=str(validation_err),
                attempts=0,
            )

        # 2. Format message body text (use pre-formatted Operator Report if detected)
        if "🚨 AERA INCIDENT REPORT" in message.body:
            body_text = message.body
        else:
            body_text = self.format_message(message)
        parse_mode = self._config.parse_mode if self._config.markdown_enabled else None

        # Determine evidence photo and report attachments
        photo_path: Optional[str] = None
        report_path: Optional[str] = message.metadata.get("report_path")

        for att in message.attachments:
            # First image attachment acts as primary evidence photo
            if "image" in att.content_type.lower():
                photo_path = att.file_path
                break

        attempts = 0
        success = False
        status = NotificationDeliveryStatus.FAILED
        error_msg: Optional[str] = None
        msg_id: Optional[str] = None

        logger.info(
            "TelegramNotifier: Starting dispatch of Event ID '%s' to bot=%s target=%s",
            message.metadata.get("event_id", "N/A"),
            mask_secret(self._config.telegram_bot_token),
            mask_secret(self._config.telegram_chat_id),
        )

        # 3. Dispatch loop with exponential backoff retries
        while attempts < self._config.retry_count:
            attempts += 1
            try:
                import os
                if self._config.send_images and photo_path and os.path.exists(photo_path):
                    # Dispatch evidence photo with emergency text caption
                    res = self._client.send_photo(
                        photo_path=photo_path,
                        caption=body_text,
                        parse_mode=parse_mode
                    )
                else:
                    # Fall back to text message only (e.g. if photo is missing/disabled)
                    res = self._client.send_message(
                        text=body_text,
                        parse_mode=parse_mode
                    )
                
                # Dispatch succeeded
                success = True
                status = NotificationDeliveryStatus.SUCCESS
                msg_id = str(res.get("result", {}).get("message_id", ""))
                error_msg = None
                break

            except Exception as dispatch_err:
                error_msg = str(dispatch_err)
                logger.warning(
                    "TelegramNotifier: Dispatch attempt %d failed: %s",
                    attempts,
                    error_msg,
                )
                if attempts < self._config.retry_count:
                    delay = self._config.retry_delay * (2 ** attempts)
                    logger.info("TelegramNotifier: Backing off for %.1f seconds before next attempt...", delay)
                    time.sleep(delay)

        latency = time.time() - start_time
        logger.info(
            "TelegramNotifier: Primary dispatch completed in %.2fs. status=%s attempts=%d msg_id=%s",
            latency,
            status.value,
            attempts,
            msg_id,
        )

        # 4. Dispatch detailed report file document (if enabled and primary succeeded)
        if success and self._config.send_reports and report_path:
            try:
                logger.debug("TelegramNotifier: Dispatching incident report file: %s", report_path)
                self._client.send_document(
                    doc_path=report_path,
                    caption="Detailed Incident Report Log"
                )
                logger.info("TelegramNotifier: Report document file sent successfully.")
            except Exception as doc_err:
                # Log report file failures as non-blocking warnings so alert delivery is not interrupted
                logger.warning(
                    "TelegramNotifier: Failed to dispatch report document (non-blocking): %s",
                    doc_err,
                )

        # Compile final outcome result
        return NotificationResult(
            success=success,
            status=status,
            channel=self.name,
            timestamp=time.time(),
            latency=latency,
            error_message=error_msg,
            attempts=attempts,
            message_id=msg_id,
        )

    def close(self) -> None:
        """Close HTTP session client connection resources."""
        self._client.close()
