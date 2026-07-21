"""Camera persistence repository for the AERA Camera Management System.

Implements direct SQLite database queries to storage/cameras.db to store, update,
and manage registered camera feeds.
"""

import sqlite3
import os
import time
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class CameraRepository:
    """Manages the persistence of camera entities in an SQLite database."""

    def __init__(self, db_path: str = "storage/cameras.db") -> None:
        """Initialize the repository and database tables."""
        if not os.path.isabs(db_path) and not os.path.exists(db_path):
            alt_path = os.path.join("edge", db_path)
            if os.path.exists(os.path.dirname(alt_path)):
                db_path = alt_path
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Acquire a thread-safe connection to the SQLite database.

        Returns:
            An active sqlite3.Connection instance with row_factory enabled.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create the cameras table structure if it is missing."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cameras (
                    camera_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL,
                    location TEXT,
                    description TEXT,
                    source TEXT NOT NULL UNIQUE,
                    port INTEGER,
                    username TEXT,
                    password TEXT,
                    rtsp_path TEXT,
                    enabled INTEGER DEFAULT 1,
                    created_time REAL,
                    updated_time REAL,
                    last_seen REAL
                )
            """)
            conn.commit()

    def add_camera(self, camera_data: Dict[str, Any]) -> None:
        """Insert a newly registered camera into the database.

        Args:
            camera_data: Attributes dict containing all required table fields.
        """
        now = time.time()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO cameras (
                    camera_id, name, type, location, description, source, port,
                    username, password, rtsp_path, enabled, created_time, updated_time, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                camera_data["camera_id"],
                camera_data["name"],
                camera_data["type"],
                camera_data.get("location"),
                camera_data.get("description"),
                camera_data["source"],
                camera_data.get("port"),
                camera_data.get("username"),
                camera_data.get("password"),
                camera_data.get("rtsp_path"),
                1 if camera_data.get("enabled", True) else 0,
                now,
                now,
                0.0
            ))
            conn.commit()

    def update_camera(self, camera_id: str, camera_data: Dict[str, Any]) -> None:
        """Update fields for a registered camera record.

        Args:
            camera_id: Unique identifier for the camera record.
            camera_data: Dictionary containing fields to modify.
        """
        now = time.time()
        updates = []
        params = []
        
        valid_fields = [
            "name", "type", "location", "description", "source", 
            "port", "username", "password", "rtsp_path", "enabled"
        ]
        
        for key in valid_fields:
            if key in camera_data:
                updates.append(f"{key} = ?")
                val = camera_data[key]
                if key == "enabled":
                    val = 1 if val else 0
                params.append(val)
        
        if not updates:
            return

        updates.append("updated_time = ?")
        params.append(now)
        params.append(camera_id)

        query = f"UPDATE cameras SET {', '.join(updates)} WHERE camera_id = ?"
        with self._get_connection() as conn:
            conn.execute(query, tuple(params))
            conn.commit()

    def get_camera(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a registered camera record by camera_id.

        Args:
            camera_id: Unique identifier.

        Returns:
            The database record dict, or None if not found.
        """
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM cameras WHERE camera_id = ?", (camera_id,)).fetchone()
            if row:
                return dict(row)
        return None

    def get_camera_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a registered camera record by name.

        Args:
            name: Camera Name.

        Returns:
            The database record dict, or None if not found.
        """
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM cameras WHERE name = ?", (name,)).fetchone()
            if row:
                return dict(row)
        return None

    def get_camera_by_source(self, source: str) -> Optional[Dict[str, Any]]:
        """Retrieve a registered camera record by source.

        Args:
            source: Source URL or local webcam ID.

        Returns:
            The database record dict, or None if not found.
        """
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM cameras WHERE source = ?", (source,)).fetchone()
            if row:
                return dict(row)
        return None

    def list_cameras(self) -> List[Dict[str, Any]]:
        """Retrieve all registered camera records.

        Returns:
            A list of dictionary camera records.
        """
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM cameras").fetchall()
            return [dict(r) for r in rows]

    def delete_camera(self, camera_id: str) -> None:
        """Delete a registered camera record by camera_id.

        Args:
            camera_id: Unique identifier.
        """
        with self._get_connection() as conn:
            conn.execute("DELETE FROM cameras WHERE camera_id = ?", (camera_id,))
            conn.commit()
