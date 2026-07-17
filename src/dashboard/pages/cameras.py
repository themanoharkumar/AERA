"""Live Cameras page for the AERA Dashboard.

Renders camera filtering options and a responsive layout grid of active video streams.
Supports pseudo-realtime live feed polling using native Streamlit widgets.
"""

import streamlit as st
import time
from src.dashboard.services.backend import BackendGateway
from src.dashboard.components.camera_card import render_camera_card
from src.camera.camera import CameraStatus

def render_page(gateway: BackendGateway) -> None:
    """Render the Live Cameras monitoring page.

    Args:
        gateway: Caching backend service gateway.
    """
    # 1. Fetch camera records
    cameras = gateway.list_cameras()
    
    # 2. Render Page Controls (Status Filters & Live Feed Auto-refresh)
    col_filter, col_toggle = st.columns([3, 1])
    
    with col_filter:
        status_options = ["ALL", "STREAMING", "CONNECTED", "DISCONNECTED"]
        selected_status = st.radio(
            "Filter Feeds by Status:",
            status_options,
            horizontal=True,
            label_visibility="collapsed"
        )

    with col_toggle:
        # Toggle to enable active layout reruns simulating real-time streams
        auto_refresh = st.toggle("🎥 Active Live Feeds", value=False, help="Continuously poll and refresh camera frame buffers.")

    # Apply camera status filtering
    filtered_cams = cameras
    if selected_status != "ALL":
        filtered_cams = [
            c for c in cameras 
            if c.status.value.upper() == selected_status
        ]

    st.divider()

    # 3. Render Camera Grid
    active_placeholders = []
    if filtered_cams:
        # 2-column responsive grid
        grid_cols = st.columns(2)
        for idx, cam in enumerate(filtered_cams):
            with grid_cols[idx % 2]:
                placeholder = render_camera_card(gateway, cam)
                if placeholder is not None:
                    active_placeholders.append((cam.camera_id, placeholder))
    else:
        st.warning(f"📷 **No cameras found** matching status filter: *{selected_status}*.")

    # 4. Handle auto-refresh in-place updates loop
    if auto_refresh and active_placeholders:
        # Run smooth, in-place frame buffer updates without page-level reload
        while True:
            for camera_id, placeholder in active_placeholders:
                frame, is_active = gateway.get_latest_frame(camera_id)
                if frame is not None:
                    placeholder.image(frame, channels="BGR", use_container_width=True)
            # Sleep 100ms for a smooth 10 FPS experience
            time.sleep(0.1)
