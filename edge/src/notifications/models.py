"""Notification data models for the AERA notification subsystem."""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from dotenv import load_dotenv

from src.notifications.exceptions import NotificationConfigError
from src.notifications.client import mask_secret

class NotificationDeliveryStatus(Enum):
    """Execution states of a channel dispatch attempt."""
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    SKIPPED = "SKIPPED"


@dataclass
class NotificationConfig:
    """Configuration settings for AERA notification channels.

    Attributes:
        telegram_enabled: Global toggle to enable/disable Telegram dispatch.
        telegram_bot_token: Telegram Bot API secret authorization token.
        telegram_chat_id: Target Chat or Group identifier username/numeric ID.
        markdown_enabled: Format messages using Markdown formatting.
        send_images: Send evidence screenshots if captured.
        send_reports: Send generated Markdown reports as document files.
        retry_count: Maximum dispatch attempts before flagging delivery failure.
        retry_delay: Base delay parameter (in seconds) for exponential backoff.
        timeout: HTTP connection/read timeout (in seconds) to avoid thread blocking.
        minimum_severity: Ignore alerts with severity below this limit (LOW, MEDIUM, HIGH, CRITICAL).
        parse_mode: Default formatting parse mode ('Markdown' or 'HTML').
        silent_notifications: Send messages silently without user sound prompts.
        chat_groups: Optional list of additional chat IDs for group notifications.
    """
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    markdown_enabled: bool = True
    send_images: bool = True
    send_reports: bool = True
    retry_count: int = 3
    retry_delay: float = 2.0
    timeout: float = 5.0
    minimum_severity: str = "LOW"
    parse_mode: str = "Markdown"
    silent_notifications: bool = False
    chat_groups: List[str] = field(default_factory=list)
    attach_forensic_for_critical: bool = True
    attach_forensic_always: bool = False

    @classmethod
    def from_env(cls) -> "NotificationConfig":
        """Load and validate notification configuration parameters from environment variables."""
        # Load dotenv file
        load_dotenv()

        # Helper to parse boolean values safely
        def parse_bool(env_var: str, default: bool) -> bool:
            val = os.environ.get(env_var)
            if val is None:
                return default
            return val.strip().lower() in ("true", "1", "yes", "on")

        # 1. Parse boolean switches
        telegram_enabled = parse_bool("TELEGRAM_ENABLED", False)
        markdown_enabled = parse_bool("MARKDOWN_ENABLED", True)
        send_images = parse_bool("SEND_IMAGES", True)
        send_reports = parse_bool("SEND_REPORTS", True)
        silent_notifications = parse_bool("SILENT_NOTIFICATIONS", False)
        attach_forensic_for_critical = parse_bool("ATTACH_FORENSIC_FOR_CRITICAL", True)
        attach_forensic_always = parse_bool("ATTACH_FORENSIC_ALWAYS", False)

        # 2. Extract credential strings
        telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

        # 3. Parse and validate integer Retry count
        retry_count_raw = os.environ.get("RETRY_COUNT", "3").strip()
        try:
            retry_count = int(retry_count_raw)
            if retry_count < 0:
                raise ValueError("Retry count cannot be negative.")
        except ValueError as e:
            raise NotificationConfigError(f"Configuration value RETRY_COUNT is invalid: {e}")

        # 4. Parse and validate float Retry delay
        retry_delay_raw = os.environ.get("RETRY_DELAY", "2.0").strip()
        try:
            retry_delay = float(retry_delay_raw)
            if retry_delay <= 0.0:
                raise ValueError("Retry delay must be greater than zero.")
        except ValueError as e:
            raise NotificationConfigError(f"Configuration value RETRY_DELAY is invalid: {e}")

        # 5. Parse and validate float Timeout limits
        timeout_raw = os.environ.get("TIMEOUT", "5.0").strip()
        try:
            timeout = float(timeout_raw)
            if timeout <= 0.0:
                raise ValueError("Timeout limit must be greater than zero.")
        except ValueError as e:
            raise NotificationConfigError(f"Configuration value TIMEOUT is invalid: {e}")

        # 6. Parse and validate Severity limits
        minimum_severity = os.environ.get("MINIMUM_SEVERITY", "LOW").strip().upper()
        if minimum_severity not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            raise NotificationConfigError(
                f"Configuration value MINIMUM_SEVERITY is invalid: {minimum_severity}. "
                "Must be one of: LOW, MEDIUM, HIGH, CRITICAL."
            )

        parse_mode = os.environ.get("PARSE_MODE", "Markdown").strip()

        # Validate that credentials exist if Telegram dispatch is enabled
        if telegram_enabled:
            if not telegram_bot_token:
                raise NotificationConfigError("Missing TELEGRAM_BOT_TOKEN environment variable.")
            if not telegram_chat_id:
                raise NotificationConfigError("Missing TELEGRAM_CHAT_ID environment variable.")

        return cls(
            telegram_enabled=telegram_enabled,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            markdown_enabled=markdown_enabled,
            send_images=send_images,
            send_reports=send_reports,
            retry_count=retry_count,
            retry_delay=retry_delay,
            minimum_severity=minimum_severity,
            parse_mode=parse_mode,
            silent_notifications=silent_notifications,
            attach_forensic_for_critical=attach_forensic_for_critical,
            attach_forensic_always=attach_forensic_always,
        )

    def get_debug_summary(self) -> str:
        """Return a debug summary with masked sensitive values.

        Returns:
            Formatted configuration debug string.
        """
        masked_token = mask_secret(self.telegram_bot_token)
        masked_chat = mask_secret(self.telegram_chat_id)
        return (
            f"NotificationConfig("
            f"telegram_enabled={self.telegram_enabled}, "
            f"telegram_bot_token='{masked_token}', "
            f"telegram_chat_id='{masked_chat}', "
            f"markdown_enabled={self.markdown_enabled}, "
            f"send_images={self.send_images}, "
            f"send_reports={self.send_reports}, "
            f"retry_count={self.retry_count}, "
            f"retry_delay={self.retry_delay}, "
            f"timeout={self.timeout}, "
            f"minimum_severity='{self.minimum_severity}', "
            f"attach_forensic_for_critical={self.attach_forensic_for_critical}, "
            f"attach_forensic_always={self.attach_forensic_always}"
            f")"
        )


@dataclass
class NotificationAttachment:
    """Represents a media or document file linked to a notification.

    Attributes:
        file_path: The physical location of the attachment on the local disk.
        content_type: MIME media type (e.g. 'image/jpeg', 'video/mp4').
        filename: Optional override of the original filename for presentation.
        description: Optional textual label describing the media context.
    """
    file_path: str
    content_type: str
    filename: Optional[str] = None
    description: Optional[str] = None


@dataclass
class NotificationMessage:
    """Represents the structured alert dispatch request.

    Attributes:
        recipient: Target delivery identifier (e.g., chat ID, email address).
        subject: Heading or short summary of the event.
        body: Plaintext or markdown formatted detail log.
        urgency: Level of emergency importance (e.g. 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL').
        attachments: Associated visual files or logs related to the incident report.
        metadata: Custom key-value pairs representing context details (e.g. confidence, camera).
    """
    recipient: str
    subject: str
    body: str
    urgency: str = "MEDIUM"
    attachments: List[NotificationAttachment] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class NotificationResult:
    """Represents the final outcome of a notifier channel dispatch execution.

    Attributes:
        success: True if the notification was delivered successfully, False otherwise.
        status: The final execution state of the notification.
        channel: The name of the notifier channel that handled dispatch.
        timestamp: Epoch timestamp representing when the result was processed.
        latency: Execution latency duration (in seconds).
        error_message: Optional traceback or error explanation.
        attempts: Number of dispatch executions attempted.
        message_id: Optional Telegram message identifier returned by the API.
    """
    success: bool
    status: NotificationDeliveryStatus
    channel: str
    timestamp: float
    latency: float
    error_message: Optional[str] = None
    attempts: int = 1
    message_id: Optional[str] = None
