"""AERA Alert System package.

This package exposes delivery notification channels, tracks dispatch logging history,
implements retry logic, and validates report payloads.
"""

from src.alert.alert import Alert
from src.alert.channels import ConsoleNotifier
from src.alert.exceptions import AlertError, ChannelError, NotificationError
from src.alert.history import AlertHistory, HistoryRecord
from src.alert.manager import AlertManager
from src.alert.notifier import BaseNotifier

__all__ = [
    "Alert",
    "AlertManager",
    "BaseNotifier",
    "ConsoleNotifier",
    "AlertHistory",
    "HistoryRecord",
    "AlertError",
    "NotificationError",
    "ChannelError",
]
