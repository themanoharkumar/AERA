"""Base abstract notifier definitions for the AERA notification subsystem."""

from abc import ABC, abstractmethod
from src.notifications.models import NotificationMessage, NotificationResult


class BaseNotifier(ABC):
    """Abstract base class for all concrete notification dispatch channels.

    Ensures consistent API boundaries, input validation rules, and outcome results
    for distinct notification integrations (e.g. Telegram, Email, console).
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
    def send(self, message: NotificationMessage) -> NotificationResult:
        """Execute delivery of the notification message to the target recipient.

        Args:
            message: The NotificationMessage object containing payload and attachments.

        Returns:
            A NotificationResult representing the outcome.

        Raises:
            NotificationDeliveryError: If channel communication fails.
            NotificationValidationError: If structural message variables are corrupt.
            NotificationConfigError: If credentials or configurations are missing.
        """
        pass

    @abstractmethod
    def validate(self, message: NotificationMessage) -> None:
        """Perform validation on the notification message before sending.

        Args:
            message: The NotificationMessage payload to validate.

        Raises:
            NotificationValidationError: If validation checks fail.
        """
        pass
