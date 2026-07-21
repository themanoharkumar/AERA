"""Telegram HTTP API transport client implementation."""

import logging
import os
import requests
from typing import Optional

from src.notifications.exceptions import (
    NotificationConfigError,
    NotificationDeliveryError,
)

logger = logging.getLogger(__name__)


def mask_secret(secret: str) -> str:
    """Mask a sensitive token or ID for safe logging.

    Args:
        secret: Unmasked credentials string.

    Returns:
        A partially obfuscated string representation.
    """
    if not secret:
        return ""
    str_val = str(secret)
    if len(str_val) > 8:
        return f"{str_val[:4]}...{str_val[-4:]}"
    return "****"


class TelegramClient:
    """Handles raw HTTP communications with the Telegram Bot API.

    Encapsulates connection timeouts, request packaging, and response processing.
    """

    def __init__(self, bot_token: str, chat_id: str, timeout: float = 5.0) -> None:
        """Initialize the Telegram transport client.

        Args:
            bot_token: Bot API token.
            chat_id: Recipient chat identifier.
            timeout: Connection/read timeout (in seconds).
        """
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._timeout = timeout
        self._session = requests.Session()
        self._base_url = f"https://api.telegram.org/bot{self._bot_token}"

    def _execute_post(self, endpoint: str, payload: dict, files: Optional[dict] = None) -> dict:
        """Send a POST request to the Telegram Bot API endpoint.

        Args:
            endpoint: API endpoint name (e.g. 'sendMessage').
            payload: Parameters payload directory.
            files: Optional files dict for multipart/form-data.

        Returns:
            The parsed JSON response dict.

        Raises:
            NotificationConfigError: If credentials or chat targets are rejected.
            NotificationDeliveryError: If connection or server errors occur.
        """
        url = f"{self._base_url}/{endpoint}"
        masked_token = mask_secret(self._bot_token)
        masked_chat = mask_secret(payload.get("chat_id", self._chat_id))

        logger.debug(
            "TelegramClient: Posting to endpoint '%s' using bot=%s target=%s",
            endpoint,
            masked_token,
            masked_chat,
        )

        try:
            response = self._session.post(
                url,
                data=payload,
                files=files,
                timeout=self._timeout
            )
        except requests.exceptions.Timeout as e:
            logger.error("TelegramClient timeout occurred during POST: %s", e)
            raise NotificationDeliveryError(f"Request timed out after {self._timeout}s.")
        except requests.exceptions.ConnectionError as e:
            logger.error("TelegramClient connection error occurred: %s", e)
            raise NotificationDeliveryError("Network connection failed. Bot API server unreachable.")
        except Exception as e:
            logger.error("TelegramClient unexpected post exception: %s", e)
            raise NotificationDeliveryError(f"Unexpected transport failure: {e}")

        # Check for HTTP status codes
        status_code = response.status_code
        logger.debug("TelegramClient received HTTP status code: %d", status_code)

        try:
            res_json = response.json()
        except ValueError:
            res_json = {}

        if status_code == 200:
            return res_json

        # Translate Telegram error responses
        error_description = res_json.get("description", "Unknown Telegram API Error")
        logger.error(
            "Telegram API error (HTTP %d): %s | Raw response: %s",
            status_code,
            error_description,
            res_json,
        )

        if status_code == 401:
            raise NotificationConfigError(f"Unauthorized. The provided Bot Token is invalid: {error_description}")
        if status_code in (400, 403):
            raise NotificationConfigError(f"Rejected. Verify recipient Chat ID or Bot permission limits: {error_description}")
        if status_code == 429:
            retry_after = res_json.get("parameters", {}).get("retry_after", 5)
            raise NotificationDeliveryError(f"Rate limited. Telegram requests throttled. Retry after {retry_after}s.")

        raise NotificationDeliveryError(f"Telegram API delivery failed (HTTP {status_code}): {error_description}")

    def send_message(self, text: str, parse_mode: str = "Markdown") -> dict:
        """Send a standard text message.

        Args:
            text: Message body content.
            parse_mode: Message formatting mode ('Markdown', 'HTML', or None).

        Returns:
            Telegram API JSON response.
        """
        payload = {
            "chat_id": self._chat_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return self._execute_post("sendMessage", payload)

    def send_photo(self, photo_path: str, caption: str, parse_mode: str = "Markdown") -> dict:
        """Upload and send a photo with a caption.

        Args:
            photo_path: Physical location of the image file.
            caption: Captioned text associated with the photo.
            parse_mode: Caption formatting mode.

        Returns:
            Telegram API JSON response.
        """
        if not os.path.exists(photo_path):
            raise NotificationDeliveryError(f"Evidence photo file not found at path: {photo_path}")

        payload = {
            "chat_id": self._chat_id,
            "caption": caption,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        with open(photo_path, "rb") as f:
            files = {"photo": (os.path.basename(photo_path), f, "image/jpeg")}
            return self._execute_post("sendPhoto", payload, files=files)

    def send_document(self, doc_path: str, caption: Optional[str] = None) -> dict:
        """Upload and send a document file.

        Args:
            doc_path: Physical location of the document.
            caption: Optional caption text.

        Returns:
            Telegram API JSON response.
        """
        if not os.path.exists(doc_path):
            raise NotificationDeliveryError(f"Report document file not found at path: {doc_path}")

        payload = {
            "chat_id": self._chat_id,
        }
        if caption:
            payload["caption"] = caption

        with open(doc_path, "rb") as f:
            files = {"document": (os.path.basename(doc_path), f, "text/markdown")}
            return self._execute_post("sendDocument", payload, files=files)

    def close(self) -> None:
        """Close the underlying HTTP session cleanly to release resources."""
        self._session.close()
