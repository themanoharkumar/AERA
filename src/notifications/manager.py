"""NotificationManager coordination layer for routing notifications."""

import logging
import threading
import time
from typing import Dict

from src.notifications.base import BaseNotifier
from src.notifications.exceptions import NotificationValidationError
from src.notifications.models import (
    NotificationConfig,
    NotificationDeliveryStatus,
    NotificationMessage,
    NotificationResult,
)

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages notifier registration and routing of messages.

    Thread-safely routes payloads to appropriate communication channels based on configurations.
    """

    def __init__(self, config: NotificationConfig) -> None:
        """Initialize the NotificationManager with configuration settings.

        Args:
            config: A NotificationConfig configuration payload.
        """
        self._config = config
        self._notifiers: Dict[str, BaseNotifier] = {}
        self._lock = threading.Lock()

    def register_notifier(self, notifier: BaseNotifier) -> None:
        """Register a notification delivery channel.

        Args:
            notifier: An instance implementing BaseNotifier.

        Raises:
            NotificationValidationError: If notifier parameter is None or name is empty.
        """
        if notifier is None:
            raise NotificationValidationError("Notifier instance cannot be None.")
        if not notifier.name:
            raise NotificationValidationError("Notifier must define a valid non-empty name property.")

        with self._lock:
            self._notifiers[notifier.name] = notifier
            logger.info("Registered notification channel: %s", notifier.name)

    def get_notifier(self, name: str) -> BaseNotifier:
        """Retrieve a registered notifier channel by name.

        Args:
            name: Identification name of the notifier channel.

        Returns:
            The notifier channel instance.

        Raises:
            KeyError: If the requested notifier is not registered.
        """
        with self._lock:
            return self._notifiers[name]

    def route_notification(self, channel_name: str, message: NotificationMessage) -> NotificationResult:
        """Deliver the message payload to the specified notifier channel if enabled.

        Args:
            channel_name: Target notifier name (e.g. 'TelegramNotifier').
            message: The NotificationMessage object payload.

        Returns:
            A NotificationResult representing the outcome.

        Raises:
            NotificationValidationError: If channel_name is empty or not registered.
        """
        if not channel_name:
            raise NotificationValidationError("Channel name cannot be empty.")

        # 1. Enforce global activation status check based on configuration
        if channel_name == "TelegramNotifier" and not self._config.telegram_enabled:
            logger.info("NotificationManager: Routing bypassed. Telegram notifications are disabled.")
            return NotificationResult(
                success=False,
                status=NotificationDeliveryStatus.SKIPPED,
                channel=channel_name,
                timestamp=time.time(),
                latency=0.0,
                error_message="Telegram notifications are globally disabled in config.",
                attempts=0,
            )

        with self._lock:
            if channel_name not in self._notifiers:
                raise NotificationValidationError(
                    f"Notifier channel '{channel_name}' is not registered."
                )
            notifier = self._notifiers[channel_name]

        # Call send without holding the manager-wide lock to prevent thread blockage
        return notifier.send(message)
