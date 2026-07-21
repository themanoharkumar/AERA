"""AERA Notification Subsystem."""

from src.notifications.adapter import TelegramNotifierAdapter
from src.notifications.base import BaseNotifier
from src.notifications.client import TelegramClient
from src.notifications.exceptions import (
    NotificationConfigError,
    NotificationDeliveryError,
    NotificationException,
    NotificationValidationError,
)
from src.notifications.manager import NotificationManager
from src.notifications.models import (
    NotificationAttachment,
    NotificationConfig,
    NotificationDeliveryStatus,
    NotificationMessage,
    NotificationResult,
)
from src.notifications.telegram import TelegramNotifier

__all__ = [
    "BaseNotifier",
    "TelegramNotifier",
    "NotificationManager",
    "TelegramClient",
    "NotificationConfig",
    "TelegramNotifierAdapter",
    "NotificationAttachment",
    "NotificationDeliveryStatus",
    "NotificationMessage",
    "NotificationResult",
    "NotificationException",
    "NotificationDeliveryError",
    "NotificationValidationError",
    "NotificationConfigError",
]
