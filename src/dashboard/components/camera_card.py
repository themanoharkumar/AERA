"""Camera Card component for the AERA Dashboard.

Visualizes a single camera card, including connection controls, FPS indicators,
and a visual stream display using native Streamlit widgets.
"""

import streamlit as st
from src.dashboard.services.backend import BackendGateway
from src.camera.camera import CameraStatus, Camera

def render_camera_card(gateway: BackendGateway, camera: Camera) -> None:
    """Render a card displaying camera status, connection, and stream frames.

    Args:
        gateway: Caching backend service gateway.
        camera: The Camera entity instance.
    """
    camera_id = camera.camera_id
    status = camera.status
    
    # 1. Determine status badge text using standard Markdown color tokens
    if status == CameraStatus.STREAMING:
        status_badge = "**:green[● STREAMING]**"
    elif status in (CameraStatus.CONNECTED, CameraStatus.CONNECTING):
        status_badge = "**:blue[● CONNECTED]**"
    else:
        status_badge = "**:grey[● OFFLINE]**"

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
                    success, msg = gateway.stop_camera(camera_id)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                if st.button("Start", key=f"cam_ctrl_start_{camera_id}", use_container_width=True, type="primary"):
                    success, msg = gateway.start_camera(camera_id)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
