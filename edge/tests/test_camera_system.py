"""Unit tests for AERA Camera Registration and Management System."""

import os
import shutil
import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from src.camera.security import encrypt_password, decrypt_password
from src.camera.repository import CameraRepository
from src.camera.service import CameraService
from src.camera.manager import CameraManager
from src.camera.camera import CameraStatus


def test_password_encryption_decryption() -> None:
    """Verify passwords encrypt and decrypt correctly without data leakage."""
    plain = "rtsp_pass_123!"
    encrypted = encrypt_password(plain)
    
    assert encrypted != plain
    assert decrypt_password(encrypted) == plain
    assert decrypt_password("") == ""
    assert encrypt_password("") == ""


def test_camera_repository_crud() -> None:
    """Verify SQLite database CRUD operations work correctly."""
    db_path = "storage/test_cameras.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    repo = CameraRepository(db_path=db_path)
    
    cam_data = {
        "camera_id": "test_cam_1",
        "name": "Test Entrance",
        "type": "RTSP",
        "location": "Lobby",
        "description": "Surveillance entrance",
        "source": "rtsp://admin:pass@192.168.1.50:554/live",
        "port": 554,
        "username": "admin",
        "password": "encrypted_pass_1",
        "rtsp_path": "/live",
        "enabled": True
    }

    # Add
    repo.add_camera(cam_data)
    
    # Get
    fetched = repo.get_camera("test_cam_1")
    assert fetched is not None
    assert fetched["name"] == "Test Entrance"
    assert fetched["enabled"] == 1

    # List
    all_cams = repo.list_cameras()
    assert len(all_cams) == 1

    # Update
    repo.update_camera("test_cam_1", {"name": "Lobby Main Entrance", "enabled": False})
    updated = repo.get_camera("test_cam_1")
    assert updated["name"] == "Lobby Main Entrance"
    assert updated["enabled"] == 0

    # Delete
    repo.delete_camera("test_cam_1")
    assert repo.get_camera("test_cam_1") is None

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@patch("src.camera.stream.cv2.VideoCapture")
def test_camera_service_integration(mock_video_capture: MagicMock) -> None:
    """Verify CameraService validation, testing, and lifecycle registration rules."""
    # Setup mocks
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)
    mock_cap.get.side_effect = lambda prop: 640 if prop == 3 else (480 if prop == 4 else 30.0)
    mock_video_capture.return_value = mock_cap

    db_path = "storage/test_cameras_service.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    repo = CameraRepository(db_path=db_path)
    manager = CameraManager()
    service = CameraService(repo, manager)

    cam_form = {
        "name": "Webcam 1",
        "type": "WEBCAM",
        "source": "0",
        "location": "Server Room",
        "description": "USB Webcam",
        "enabled": True
    }

    # 1. Test Connection
    test_res = service.test_connection(cam_form)
    assert test_res["success"] is True
    assert test_res["resolution"] == "640x480"
    assert test_res["fps"] == 30.0

    # 2. Register camera
    success, msg = service.register_camera(cam_form)
    assert success is True
    
    # 3. Check persistence and manager status
    cameras = repo.list_cameras()
    assert len(cameras) == 1
    camera_id = cameras[0]["camera_id"]
    
    assert camera_id in manager._cameras
    assert manager.camera_status(camera_id) == CameraStatus.STREAMING

    # 4. Disable camera (updates status to disabled)
    success, msg = service.update_camera(camera_id, {**cam_form, "enabled": False})
    assert success is True
    assert camera_id not in manager._cameras

    # 5. Delete camera
    success, msg = service.delete_camera(camera_id)
    assert success is True
    assert len(repo.list_cameras()) == 0

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)
