"""Camera Service Layer for the AERA Camera Management System.

Integrates camera configuration validations, credentials encryption/decryption,
OpenCV connection testing and preview capture, and registers live streams into
the coordinate CameraManager.
"""

import uuid
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import cv2

from .repository import CameraRepository
from .manager import CameraManager
from .security import encrypt_password, decrypt_password

logger = logging.getLogger(__name__)


class CameraService:
    """Orchestrates camera database registrations and live stream controls."""

    def __init__(self, repository: CameraRepository, camera_manager: CameraManager) -> None:
        """Initialize CameraService.

        Args:
            repository: CameraRepository database connector.
            camera_manager: Core CameraManager stream orchestrator.
        """
        self.repository = repository
        self.manager = camera_manager

    def validate_camera_config(self, data: Dict[str, Any], updating_id: Optional[str] = None) -> Tuple[bool, str]:
        """Validate input field constraints before saving.

        Args:
            data: Form input attributes.
            updating_id: Existing camera ID if editing.

        Returns:
            A tuple of (success: bool, message: str).
        """
        name = data.get("name", "").strip()
        if not name:
            return False, "Camera Name is required."
            
        cam_type = data.get("type", "").upper()
        if cam_type not in ("RTSP", "WEBCAM", "FILE", "HTTP"):
            return False, f"Unsupported camera type: {cam_type}"

        # Enforce unique names
        existing = self.repository.get_camera_by_name(name)
        if existing and existing["camera_id"] != updating_id:
            return False, f"A camera named '{name}' is already registered."

        # Enforce source URL validity
        source = self.build_source(data)
        if not source:
            return False, "Camera source configuration is empty."

        existing_src = self.repository.get_camera_by_source(source)
        if existing_src and existing_src["camera_id"] != updating_id:
            return False, f"A camera with endpoint '{source}' is already registered."

        return True, "Validation successful."

    def build_source(self, data: Dict[str, Any]) -> str:
        """Construct the connection URL or local resource index for the source.

        Args:
            data: Camera parameters dictionary.

        Returns:
            The formatted source identifier string.
        """
        cam_type = data.get("type", "").upper()
        if cam_type == "RTSP":
            username = data.get("username", "")
            password = data.get("password", "")
            ip = data.get("ip_address", "")
            port = data.get("port")
            path = data.get("rtsp_path", "")
            if path and not path.startswith("/"):
                path = "/" + path
                
            cred = ""
            if username or password:
                cred = f"{username}:{password}@"
                
            port_str = f":{port}" if port else ""
            return f"rtsp://{cred}{ip}{port_str}{path}"
        elif cam_type == "HTTP":
            ip = data.get("ip_address", "")
            port = data.get("port")
            path = data.get("rtsp_path", "")
            if path and not path.startswith("/"):
                path = "/" + path
            port_str = f":{port}" if port else ""
            return f"http://{ip}{port_str}{path}"
        elif cam_type == "WEBCAM":
            return str(data.get("source", "0"))
        elif cam_type == "FILE":
            return str(data.get("source", ""))
        return str(data.get("source", ""))

    def test_connection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify stream accessibility by reading a single frame.

        Args:
            data: Camera connection fields form.

        Returns:
            A results dictionary (success, latency, resolution, fps, frame).
        """
        source = self.build_source(data)
        cam_type = data.get("type", "").upper()
        
        logger.info("Testing connection to source: %s", source)
        try:
            if cam_type == "WEBCAM" and source.isdigit():
                cap = cv2.VideoCapture(int(source))
            else:
                cap = cv2.VideoCapture(source)

            # Set connection timeout behavior if RTSP
            if cam_type == "RTSP":
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)

            if not cap.isOpened():
                if cam_type == "RTSP" and "@" in source:
                    return {"success": False, "reason": "Authentication Failed"}
                return {"success": False, "reason": "Camera Offline"}

            t_before = time.time()
            ret, frame = cap.read()
            latency = (time.time() - t_before) * 1000.0
            
            if not ret or frame is None:
                cap.release()
                return {"success": False, "reason": "Unable to Decode Stream"}

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30.0

            cap.release()
            return {
                "success": True,
                "resolution": f"{width}x{height}",
                "fps": fps,
                "latency": latency,
                "frame": frame
            }
        except Exception as e:
            return {"success": False, "reason": f"Timeout: {str(e)}"}

    def register_camera(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate, encrypt, persist to SQLite, and register into live CameraManager.

        Args:
            data: Form parameters dictionary.

        Returns:
            A tuple of (success: bool, message: str).
        """
        camera_id = data.get("camera_id") or ("cam_" + str(uuid.uuid4())[:8])
        success, msg = self.validate_camera_config(data, updating_id=camera_id)
        if not success:
            return False, msg

        source = self.build_source(data)
        password_plain = data.get("password", "")
        password_encrypted = encrypt_password(password_plain) if password_plain else ""

        db_data = {
            "camera_id": camera_id,
            "name": data["name"],
            "type": data["type"],
            "location": data.get("location", ""),
            "description": data.get("description", ""),
            "source": source,
            "port": data.get("port"),
            "username": data.get("username", ""),
            "password": password_encrypted,
            "rtsp_path": data.get("rtsp_path", ""),
            "enabled": data.get("enabled", True)
        }

        try:
            self.repository.add_camera(db_data)
            logger.info("Camera registered in SQLite DB: %s (ID: %s)", data["name"], camera_id)

            if db_data["enabled"]:
                self.manager.register_camera(
                    camera_id=camera_id,
                    name=db_data["name"],
                    source=source,
                    metadata={
                        "health_status": "healthy",
                        "reconnect_count": 0,
                        "last_error": "",
                        "measured_fps": 0.0,
                        "latency": 0.0
                    }
                )
                self.manager.start_camera(camera_id)
                logger.info("Started camera pipeline stream: %s", camera_id)

            return True, f"Camera '{data['name']}' successfully registered."
        except Exception as e:
            logger.error("Failed to register camera: %s", e)
            return False, f"Registration failed: {str(e)}"

    def update_camera(self, camera_id: str, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Update configurations, executing hot restarts of live manager stream feeds.

        Args:
            camera_id: Unique database key identifier.
            data: Form parameters dictionary.

        Returns:
            A tuple of (success: bool, message: str).
        """
        success, msg = self.validate_camera_config(data, updating_id=camera_id)
        if not success:
            return False, msg

        curr = self.repository.get_camera(camera_id)
        if not curr:
            return False, "Camera record not found."

        source = self.build_source(data)
        password_plain = data.get("password", "")
        
        # Check if credential changed, if so encrypt it
        if password_plain and password_plain != decrypt_password(curr.get("password", "")):
            password_encrypted = encrypt_password(password_plain)
            logger.info("Credential updated for camera %s", camera_id)
        else:
            password_encrypted = curr.get("password", "")

        db_data = {
            "name": data["name"],
            "type": data["type"],
            "location": data.get("location", ""),
            "description": data.get("description", ""),
            "source": source,
            "port": data.get("port"),
            "username": data.get("username", ""),
            "password": password_encrypted,
            "rtsp_path": data.get("rtsp_path", ""),
            "enabled": data.get("enabled", True)
        }

        try:
            self.repository.update_camera(camera_id, db_data)
            logger.info("Camera updated in SQLite DB: %s (ID: %s)", data["name"], camera_id)

            is_active = camera_id in self.manager._cameras
            should_be_active = db_data["enabled"]

            if is_active:
                self.manager.stop_camera(camera_id)
                self.manager.remove_camera(camera_id)
                logger.info("Stopped old stream for hot-update: %s", camera_id)

            if should_be_active:
                self.manager.register_camera(
                    camera_id=camera_id,
                    name=db_data["name"],
                    source=source,
                    metadata={
                        "health_status": "healthy",
                        "reconnect_count": 0,
                        "last_error": "",
                        "measured_fps": 0.0,
                        "latency": 0.0
                    }
                )
                self.manager.start_camera(camera_id)
                logger.info("Started updated camera stream: %s", camera_id)

            return True, f"Camera '{data['name']}' successfully updated."
        except Exception as e:
            logger.error("Failed to update camera %s: %s", camera_id, e)
            return False, f"Update failed: {str(e)}"

    def delete_camera(self, camera_id: str) -> Tuple[bool, str]:
        """Stop, disconnect, and completely remove camera from database and memory.

        Args:
            camera_id: Unique key identifier.

        Returns:
            A tuple of (success: bool, message: str).
        """
        try:
            if camera_id in self.manager._cameras:
                self.manager.stop_camera(camera_id)
                self.manager.remove_camera(camera_id)
                logger.info("Live stream removed for deletion: %s", camera_id)

            self.repository.delete_camera(camera_id)
            logger.info("Camera deleted from DB: %s", camera_id)
            return True, "Camera successfully deleted."
        except Exception as e:
            logger.error("Failed to delete camera %s: %s", camera_id, e)
            return False, f"Deletion failed: {str(e)}"

    def list_cameras(self) -> List[Dict[str, Any]]:
        """Retrieve all camera records from database repository.

        Returns:
            List of camera dictionaries.
        """
        return self.repository.list_cameras()
