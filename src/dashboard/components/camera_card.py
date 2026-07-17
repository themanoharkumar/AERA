"""Camera Card component for the AERA Dashboard.

Visualizes a single camera card, including connection controls, FPS indicators,
and a visual stream display using native Streamlit widgets.
"""

import streamlit as st
from typing import Any
from src.dashboard.services.backend import BackendGateway
from src.camera.camera import CameraStatus, Camera

def render_camera_card(gateway: BackendGateway, camera: Camera) -> Any:
    """Render a card displaying camera status, connection, and stream frames.

    Args:
        gateway: Caching backend service gateway.
        camera: The Camera entity instance.
    """
    camera_id = camera.camera_id
    status = camera.status

    # Initialize error tracking set in session state if missing
    if "camera_errors" not in st.session_state:
        st.session_state.camera_errors = set()
    
    # 1. Determine status badge text using standard Markdown color tokens and enhanced mappings
    if camera_id in st.session_state.camera_errors and status != CameraStatus.STREAMING:
        status_badge = "**:red[● Error]**"
    elif status == CameraStatus.STREAMING:
        status_badge = "**:green[● Streaming]**"
    elif status == CameraStatus.CONNECTING:
        status_badge = "**:orange[● Connecting]**"
    elif status == CameraStatus.CONNECTED:
        status_badge = "**:blue[● Initializing]**"
    elif status == CameraStatus.RECONNECTING:
        status_badge = "**:orange[● Reconnecting]**"
    else:
        status_badge = "**:grey[● Stopped]**"

    # Everything belongs inside one clean card (container with border)
    with st.container(border=True):
        # Header layout
        col_name, col_badge = st.columns([2, 1])
        with col_name:
            st.markdown(f"📹 **{camera.name}**")
        with col_badge:
            st.markdown(status_badge)

        # Live Feed Placeholder / Frame display
        feed_placeholder = st.empty()

        if status == CameraStatus.STREAMING:
            frame, is_active = gateway.get_latest_frame(camera_id)
            if frame is not None:
                feed_placeholder.image(frame, channels="BGR", use_container_width=True)
            else:
                feed_placeholder.info("🔄 Connecting to live feed...")
        else:
            feed_placeholder.warning("📹 Camera Feed Offline")

        # Telemetry metrics & action buttons
        fps_val = camera.metadata.get("fps", 0.0) if camera.metadata else 0.0
        last_det = camera.metadata.get("last_detection", "None") if camera.metadata else "None"

        col_info, col_btn = st.columns([2, 1])
        with col_info:
            st.caption(f"**FPS:** {fps_val:.1f}")
            st.caption(f"**Last Event:** {last_det}")

        with col_btn:
            if status == CameraStatus.STREAMING:
                if st.button("Stop", key=f"cam_ctrl_stop_{camera_id}", use_container_width=True):
                    with st.status("Stopping stream...", expanded=True) as status_box:
                        st.write("Releasing resources...")
                        success, msg = gateway.stop_camera(camera_id)
                        if success:
                            status_box.update(label="Stopped", state="complete")
                            st.success(msg)
                            st.rerun()
                        else:
                            status_box.update(label="Error releasing stream resources", state="error")
                            st.error(msg)
            else:
                if st.button("Start", key=f"cam_ctrl_start_{camera_id}", use_container_width=True, type="primary"):
                    with st.status("Connecting camera...", expanded=True) as status_box:
                        st.write("Initializing stream...")
                        st.write("Loading detector...")
                        success, msg = gateway.start_camera(camera_id)
                        if success:
                            # Clear error tracking on success
                            st.session_state.camera_errors.discard(camera_id)
                            status_box.update(label="Ready", state="complete")
                            st.success(msg)
                            st.rerun()
                        else:
                            # Track error status
                            st.session_state.camera_errors.add(camera_id)
                            status_box.update(label="Error initiating camera connection", state="error")
                            st.error(msg)
    return feed_placeholder if status == CameraStatus.STREAMING else None
