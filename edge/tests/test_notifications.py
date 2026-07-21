"""Comprehensive integration and unit tests for the AERA notification subsystem."""

import os
from unittest.mock import MagicMock, patch
import pytest
import requests

from src.notifications import (
    NotificationAttachment,
    NotificationConfig,
    NotificationConfigError,
    NotificationDeliveryStatus,
    NotificationException,
    NotificationManager,
    NotificationMessage,
    NotificationResult,
    NotificationValidationError,
    TelegramClient,
    TelegramNotifier,
    TelegramNotifierAdapter,
)
from src.notifications.client import mask_secret


def test_exceptions_raise():
    """Verify notification custom exception hierarchies raise correctly."""
    with pytest.raises(NotificationException):
        raise NotificationValidationError("Test validation error")

    with pytest.raises(NotificationException):
        raise NotificationConfigError("Test configuration error")


def test_models_instantiation():
    """Verify that dataclass models instantiate with expected fields and default values."""
    attachment = NotificationAttachment(
        file_path="/path/to/evidence.jpg",
        content_type="image/jpeg",
        filename="custom_screenshot.jpg",
        description="Active Fire Alert Details",
    )
    assert attachment.file_path == "/path/to/evidence.jpg"
    assert attachment.content_type == "image/jpeg"
    assert attachment.filename == "custom_screenshot.jpg"
    assert attachment.description == "Active Fire Alert Details"

    message = NotificationMessage(
        recipient="@AERA_Incident_Ops",
        subject="Smoke Detected",
        body="Subsystem alerts triggered on Cam 0",
        urgency="HIGH",
        attachments=[attachment],
    )
    assert message.recipient == "@AERA_Incident_Ops"
    assert message.subject == "Smoke Detected"
    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "custom_screenshot.jpg"

    result = NotificationResult(
        success=True,
        status=NotificationDeliveryStatus.SUCCESS,
        channel="TelegramNotifier",
        timestamp=123456.0,
        latency=0.45,
    )
    assert result.success is True
    assert result.status == NotificationDeliveryStatus.SUCCESS
    assert result.channel == "TelegramNotifier"
    assert result.latency == 0.45


def test_telegram_config_validation():
    """Verify validation boundaries of the TelegramNotifier based on config."""
    # Test unconfigured token
    config_no_token = NotificationConfig(telegram_bot_token="", telegram_chat_id="chat")
    notifier_no_token = TelegramNotifier(config_no_token)
    msg = NotificationMessage(recipient="chat", subject="Title", body="Content")
    with pytest.raises(NotificationConfigError, match="bot token is not configured"):
        notifier_no_token.validate(msg)

    # Test unconfigured chat ID
    config_no_chat = NotificationConfig(telegram_bot_token="token", telegram_chat_id="")
    notifier_no_chat = TelegramNotifier(config_no_chat)
    with pytest.raises(NotificationConfigError, match="chat identifier is not configured"):
        notifier_no_chat.validate(msg)


def test_notification_config_from_env_validation(monkeypatch):
    """Verify load_dotenv validation triggers for invalid parameters."""
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "my_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "my_chat")

    # Invalid retry count
    monkeypatch.setenv("RETRY_COUNT", "-5")
    with pytest.raises(NotificationConfigError, match="RETRY_COUNT"):
        NotificationConfig.from_env()

    # Invalid retry delay
    monkeypatch.setenv("RETRY_COUNT", "3")
    monkeypatch.setenv("RETRY_DELAY", "0.0")
    with pytest.raises(NotificationConfigError, match="RETRY_DELAY"):
        NotificationConfig.from_env()

    # Invalid timeout
    monkeypatch.setenv("RETRY_DELAY", "2.0")
    monkeypatch.setenv("TIMEOUT", "-1.0")
    with pytest.raises(NotificationConfigError, match="TIMEOUT"):
        NotificationConfig.from_env()

    # Invalid severity
    monkeypatch.setenv("TIMEOUT", "5.0")
    monkeypatch.setenv("MINIMUM_SEVERITY", "CRIT")
    with pytest.raises(NotificationConfigError, match="MINIMUM_SEVERITY"):
        NotificationConfig.from_env()



def test_telegram_client_send_message_mock():
    """Verify TelegramClient sends text messages to the correct API endpoint."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 999}}

    with patch("requests.Session.post", return_value=mock_response) as mock_post:
        client = TelegramClient(bot_token="test_token", chat_id="12345")
        res = client.send_message("Hello World")
        assert res["result"]["message_id"] == 999
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "bottest_token/sendMessage" in args[0]
        assert kwargs["data"]["chat_id"] == "12345"
        assert kwargs["data"]["text"] == "Hello World"


def test_telegram_client_send_photo_mock(tmp_path):
    """Verify TelegramClient executes multipart photo uploads to the sendPhoto API endpoint."""
    photo_file = tmp_path / "evidence.jpg"
    photo_file.write_bytes(b"dummy_image_bytes")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 1001}}

    with patch("requests.Session.post", return_value=mock_response) as mock_post:
        client = TelegramClient(bot_token="test_token", chat_id="12345")
        res = client.send_photo(str(photo_file), "caption_text")
        assert res["result"]["message_id"] == 1001
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "bottest_token/sendPhoto" in args[0]
        assert kwargs["data"]["chat_id"] == "12345"
        assert "photo" in kwargs["files"]


def test_telegram_client_send_document_mock(tmp_path):
    """Verify TelegramClient executes multipart document uploads to the sendDocument API endpoint."""
    doc_file = tmp_path / "report.md"
    doc_file.write_bytes(b"dummy_report_content")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 1002}}

    with patch("requests.Session.post", return_value=mock_response) as mock_post:
        client = TelegramClient(bot_token="test_token", chat_id="12345")
        res = client.send_document(str(doc_file), "report_caption")
        assert res["result"]["message_id"] == 1002
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "bottest_token/sendDocument" in args[0]
        assert kwargs["data"]["chat_id"] == "12345"
        assert "document" in kwargs["files"]


def test_telegram_notifier_retry_backoff():
    """Verify TelegramNotifier executes backoff sleep pacing under network timeout errors."""
    config = NotificationConfig(
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        retry_count=3,
        retry_delay=0.01,  # Fast tests runs
    )
    notifier = TelegramNotifier(config)
    message = NotificationMessage(recipient="chat", subject="Title", body="Content")

    with patch("requests.Session.post", side_effect=requests.exceptions.Timeout("Timed out")):
        with patch("time.sleep") as mock_sleep:
            result = notifier.send(message)
            assert result.success is False
            assert result.attempts == 3
            assert result.status == NotificationDeliveryStatus.FAILED
            assert mock_sleep.call_count == 2


def test_telegram_notifier_missing_image_fallback():
    """Verify TelegramNotifier falls back to text-only dispatches if the photo attachment file is missing."""
    config = NotificationConfig(
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        send_images=True,
    )
    notifier = TelegramNotifier(config)

    # Attachment exists but path is missing from physical disk
    att = NotificationAttachment(file_path="/missing/evidence.jpg", content_type="image/jpeg")
    message = NotificationMessage(recipient="chat", subject="Title", body="Content", attachments=[att])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 1005}}

    # The client send_photo would fail with FileNotFoundError.
    # The notifier should catch it, or validation fails, falling back to send_message.
    with patch("requests.Session.post", return_value=mock_response) as mock_post:
        result = notifier.send(message)
        assert result.success is True
        assert result.status == NotificationDeliveryStatus.SUCCESS
        assert result.message_id == "1005"
        # Verify it fallback to sendMessage instead of sendPhoto
        args, _ = mock_post.call_args
        assert "sendMessage" in args[0]


def test_telegram_notifier_masked_secrets():
    """Verify that credentials tokens and chat IDs are masked correctly in log entries."""
    assert mask_secret("123456:ABCdefGHIjkl") == "1234...Ijkl"
    assert mask_secret("123") == "****"
    assert mask_secret("") == ""


def test_manager_routing_disabled_channel():
    """Verify NotificationManager skips dispatches when a channel is globally disabled."""
    config = NotificationConfig(telegram_enabled=False)
    manager = NotificationManager(config)
    notifier = TelegramNotifier(config)
    manager.register_notifier(notifier)

    message = NotificationMessage(recipient="chat", subject="Title", body="Content")
    result = manager.route_notification("TelegramNotifier", message)
    assert result.success is False
    assert result.status == NotificationDeliveryStatus.SKIPPED
    assert "disabled" in result.error_message


def test_telegram_notifier_adapter_routing():
    """Verify that TelegramNotifierAdapter converts AERA Report objects and routes message cleanly."""
    config = NotificationConfig(
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
    )
    notification_manager = NotificationManager(config)

    mock_notifier = MagicMock()
    mock_notifier.name = "TelegramNotifier"
    mock_notifier.send.return_value = NotificationResult(
        success=True,
        status=NotificationDeliveryStatus.SUCCESS,
        channel="TelegramNotifier",
        timestamp=123.0,
        latency=0.01,
    )
    notification_manager.register_notifier(mock_notifier)

    adapter = TelegramNotifierAdapter(
        notification_manager=notification_manager,
        recipient="chat",
        coordinator_evidence_manager=None,
    )

    from src.report.report import Report
    report = Report(
        report_id="REP-123",
        event_id="EVT-123",
        decision_id="DEC-123",
        evidence_id="EVI-123",
        title="FIRE DETECTED",
        summary="A fire was evaluated at Camera 1",
        timestamp=12345.0,
        metadata={"camera_id": "Cam_1", "severity": "HIGH"},
    )

    success = adapter.send_notification(report)
    assert success is True
    mock_notifier.send.assert_called_once()
    msg = mock_notifier.send.call_args[0][0]
    assert msg.recipient == "chat"
    assert msg.subject == "FIRE DETECTED"
    assert msg.metadata["event_id"] == "EVT-123"
    assert msg.metadata["camera"] == "Cam_1"
    assert msg.metadata["severity"] == "HIGH"


def test_notification_decision_matrix():
    """Verify severity routing decision matrix: LOW, HIGH, and CRITICAL rules."""
    config = NotificationConfig(
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        send_images=True,
        attach_forensic_for_critical=True,
        attach_forensic_always=False
    )
    manager = NotificationManager(config)

    mock_notifier = MagicMock()
    mock_notifier.name = "TelegramNotifier"
    mock_notifier.send.return_value = NotificationResult(
        success=True,
        status=NotificationDeliveryStatus.SUCCESS,
        channel="TelegramNotifier",
        timestamp=100.0,
        latency=0.01,
    )
    manager.register_notifier(mock_notifier)

    # 1. Test LOW severity - should strip screenshot and report
    att = NotificationAttachment(file_path="image.jpg", content_type="image/jpeg")
    msg_low = NotificationMessage(
        recipient="chat",
        subject="Low Event",
        body="Body",
        urgency="LOW",
        attachments=[att],
        metadata={"report_path": "report.md"}
    )
    manager.route_notification("TelegramNotifier", msg_low)
    sent_msg = mock_notifier.send.call_args[0][0]
    assert len(sent_msg.attachments) == 0
    assert sent_msg.metadata.get("report_path") is None

    # 2. Test HIGH severity - should keep screenshot, but strip report
    mock_notifier.reset_mock()
    msg_high = NotificationMessage(
        recipient="chat",
        subject="High Event",
        body="Body",
        urgency="HIGH",
        attachments=[att],
        metadata={"report_path": "report.md"}
    )
    manager.route_notification("TelegramNotifier", msg_high)
    sent_msg = mock_notifier.send.call_args[0][0]
    assert len(sent_msg.attachments) == 1
    assert sent_msg.metadata.get("report_path") is None

    # 3. Test CRITICAL severity with attach enabled - should keep both
    mock_notifier.reset_mock()
    msg_crit = NotificationMessage(
        recipient="chat",
        subject="Critical Event",
        body="Body",
        urgency="CRITICAL",
        attachments=[att],
        metadata={"report_path": "report.md"}
    )
    manager.route_notification("TelegramNotifier", msg_crit)
    sent_msg = mock_notifier.send.call_args[0][0]
    assert len(sent_msg.attachments) == 1
    assert sent_msg.metadata.get("report_path") == "report.md"

    # 4. Test CRITICAL severity with attach disabled
    config_no_crit = NotificationConfig(
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        send_images=True,
        attach_forensic_for_critical=False,
    )
    manager_no_crit = NotificationManager(config_no_crit)
    manager_no_crit.register_notifier(mock_notifier)
    mock_notifier.reset_mock()
    manager_no_crit.route_notification("TelegramNotifier", msg_crit)
    sent_msg = mock_notifier.send.call_args[0][0]
    assert len(sent_msg.attachments) == 1
    assert sent_msg.metadata.get("report_path") is None


