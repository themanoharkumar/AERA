# AERA – AI Emergency Response Assistant

AERA is an AI-powered emergency monitoring platform that analyzes CCTV and webcam feeds to detect emergencies such as fire, smoke, falls, intrusion, and other suspicious activities.

## Features (Planned)

- Multi-camera monitoring
- Fire detection
- Smoke detection
- Fall detection
- Intrusion detection
- AI-generated incident reports
- Evidence capture
- Threat assessment
- Analytics dashboard
- Real-time alerts

## Tech Stack

- Python
- OpenCV
- PyTorch
- YOLO
- FastAPI
- Streamlit
- NumPy
- Pandas
- scikit-learn
- spaCy

Status:
🚧 Under Development

## Notifications Configuration

The notification subsystem (`src/notifications`) is governed by `NotificationConfig` parameters. Ensure the following configurations are set in environment variables or within the configuration manager:

- `TELEGRAM_ENABLED` (bool): Toggle dispatching alerts to Telegram channels.
- `TELEGRAM_BOT_TOKEN` (str): Authorized Bot Token credential (e.g. `123456:ABC...`).
- `TELEGRAM_CHAT_ID` (str): Target Chat/Group channel identifier.
- `MARKDOWN_ENABLED` (bool): Format emergency alerts in Markdown.
- `SEND_IMAGES` (bool): Attach evidence screenshots if captured.
- `SEND_REPORTS` (bool): Forward markdown reports as files.
- `RETRY_COUNT` (int): Connection/API request failure retries.
- `RETRY_DELAY` (float): Exponential backoff baseline seconds.
- `TIMEOUT` (float): HTTP request read/connection timeouts.