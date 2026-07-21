"""Live Cameras and Management page for the AERA Dashboard.

Renders active stream layout grids and provides a comprehensive camera registry
management system (Add/Edit forms, Test Connection utilities, and Enable/Disable status controls).
"""

import streamlit as st
import time
import datetime
from src.dashboard.services.backend import BackendGateway
from src.dashboard.components.camera_card import render_camera_card
from src.camera.camera import CameraStatus


def render_page(gateway: BackendGateway) -> None:
    """Render the tabbed Live Monitor and Camera Registry page.

    Args:
        gateway: Process-wide BackendGateway singleton.
    """
    st.markdown("## 📹 Camera Hub")

    # Create distinct Tab Layout
    tab_monitor, tab_registry = st.tabs(["🎥 Live Monitor", "⚙️ Camera Registry"])

    with tab_monitor:
        render_monitor_tab(gateway)

    with tab_registry:
        render_registry_tab(gateway)


def render_monitor_tab(gateway: BackendGateway) -> None:
    """Render the live streaming grid overview."""
    cameras = gateway.list_cameras()
    
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
        auto_refresh = st.toggle(
            "🎥 Active Live Feeds", 
            value=False, 
            help="Continuously poll and refresh camera frame buffers."
        )

    filtered_cams = cameras
    if selected_status != "ALL":
        filtered_cams = [
            c for c in cameras 
            if c.status.value.upper() == selected_status
        ]

    st.divider()

    active_placeholders = []
    if filtered_cams:
        grid_cols = st.columns(2)
        for idx, cam in enumerate(filtered_cams):
            with grid_cols[idx % 2]:
                placeholder = render_camera_card(gateway, cam)
                if placeholder is not None:
                    active_placeholders.append((cam.camera_id, placeholder))
    else:
        st.warning(f"📷 **No cameras found** matching status filter: *{selected_status}*.")

    if auto_refresh and active_placeholders:
        while True:
            for camera_id, placeholder in active_placeholders:
                frame, is_active = gateway.get_latest_frame(camera_id)
                if frame is not None:
                    placeholder.image(frame, channels="BGR", use_container_width=True)
            time.sleep(0.1)


def render_registry_tab(gateway: BackendGateway) -> None:
    """Render the Camera Registry listing and CRUD forms."""
    # Ensure form session state exists
    if "camera_form_mode" not in st.session_state:
        st.session_state.camera_form_mode = None
    if "camera_to_edit" not in st.session_state:
        st.session_state.camera_to_edit = None

    mode = st.session_state.camera_form_mode

    if mode in ("add", "edit"):
        render_camera_form(gateway, mode)
    else:
        # Display Add Camera trigger
        col_title, col_btn = st.columns([4, 1])
        with col_title:
            st.markdown("### 📋 Registered Surveillance Sources")
        with col_btn:
            if st.button("➕ Add Camera", use_container_width=True, type="primary"):
                st.session_state.camera_form_mode = "add"
                st.session_state.camera_to_edit = None
                st.rerun()

        # Fetch camera records
        cameras = gateway.camera_service.list_cameras()
        if not cameras:
            st.info("ℹ️ No surveillance sources registered yet. Click 'Add Camera' to begin.")
            return

        for cam in cameras:
            camera_id = cam["camera_id"]
            live_cam = gateway.coordinator.camera_manager._cameras.get(camera_id)

            # Determine stats from running thread or defaults
            if live_cam and cam["enabled"]:
                status = live_cam.status.value.upper()
                health = live_cam.metadata.get("health_status", "healthy").upper()
                fps = live_cam.metadata.get("measured_fps", 0.0)
                latency = live_cam.metadata.get("latency", 0.0)
                reconnects = live_cam.metadata.get("reconnect_count", 0)
                last_err = live_cam.metadata.get("last_error", "")
                
                last_frame_ts = live_cam.metadata.get("last_frame_time", 0.0)
                last_seen = datetime.datetime.fromtimestamp(last_frame_ts).strftime("%H:%M:%S") if last_frame_ts > 0 else "Never"
            else:
                status = "DISABLED"
                health = "OFFLINE"
                fps = 0.0
                latency = 0.0
                reconnects = 0
                last_err = ""
                last_seen = "Never"

            # Color badging
            health_color = ":green[HEALTHY]" if health == "HEALTHY" else (":orange[WARNING]" if health == "WARNING" else ":red[OFFLINE]")
            status_color = ":green[ACTIVE]" if status == "STREAMING" else (":orange[CONNECTING]" if status in ("CONNECTING", "RECONNECTING") else ":grey[DISABLED]")

            with st.container(border=True):
                col_header, col_badges = st.columns([3, 1])
                with col_header:
                    st.markdown(f"📹 **{cam['name']}** | {cam['location'] or 'No Location'}")
                    st.caption(f"ID: `{camera_id}` | Type: `{cam['type']}` | Source: `{cam['source']}`")
                with col_badges:
                    st.markdown(f"Status: {status_color}")
                    st.markdown(f"Health: {health_color}")

                # Performance telemetry sub-metrics
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                with col_m1:
                    st.caption(f"**Throughput:** {fps:.1f} FPS")
                with col_m2:
                    st.caption(f"**Latency:** {latency:.1f} ms")
                with col_m3:
                    st.caption(f"**Reconnect Count:** {reconnects}")
                with col_m4:
                    st.caption(f"**Last Seen:** {last_seen}")

                if last_err:
                    st.warning(f"⚠️ **Last Error:** {last_err}")

                # Actions row
                col_en, col_prev, col_ed, col_del = st.columns(4)
                with col_en:
                    if cam["enabled"]:
                        if st.button("Disable", key=f"btn_disable_{camera_id}", use_container_width=True):
                            # Set disabled
                            gateway.camera_service.update_camera(camera_id, {**cam, "enabled": False})
                            st.success(f"Camera '{cam['name']}' disabled successfully.")
                            st.rerun()
                    else:
                        if st.button("Enable", key=f"btn_enable_{camera_id}", use_container_width=True, type="primary"):
                            gateway.camera_service.update_camera(camera_id, {**cam, "enabled": True})
                            st.success(f"Camera '{cam['name']}' enabled successfully.")
                            st.rerun()

                with col_prev:
                    # Inline frame preview expander
                    with st.popover("Preview Feed", use_container_width=True):
                        if cam["enabled"] and status == "STREAMING":
                            frame, is_act = gateway.get_latest_frame(camera_id)
                            if frame is not None:
                                st.image(frame, channels="BGR", use_container_width=True, caption=f"Latest frame from {cam['name']}")
                            else:
                                st.caption("No frame buffer populated yet.")
                        else:
                            st.caption("Camera stream is disabled or offline.")

                with col_ed:
                    if st.button("Edit", key=f"btn_edit_{camera_id}", use_container_width=True):
                        st.session_state.camera_form_mode = "edit"
                        st.session_state.camera_to_edit = camera_id
                        st.rerun()

                with col_del:
                    if st.button("Delete", key=f"btn_delete_{camera_id}", use_container_width=True):
                        gateway.camera_service.delete_camera(camera_id)
                        st.success("Camera deleted successfully.")
                        st.rerun()


def render_camera_form(gateway: BackendGateway, mode: str) -> None:
    """Render the configuration form for adding or editing a camera."""
    camera_id = st.session_state.camera_to_edit
    
    if mode == "edit" and camera_id:
        cam_record = gateway.camera_repository.get_camera(camera_id)
        if not cam_record:
            st.error("Error: Camera record not found.")
            st.session_state.camera_form_mode = None
            st.rerun()
            return
        
        # Read decrypted password
        from src.camera.security import decrypt_password
        decrypted_pwd = decrypt_password(cam_record.get("password", ""))
        
        # Prepopulate settings
        form_name = cam_record["name"]
        form_type = cam_record["type"]
        form_loc = cam_record.get("location", "")
        form_desc = cam_record.get("description", "")
        form_ip = cam_record.get("source", "") if form_type in ("RTSP", "HTTP") else ""
        form_port = cam_record.get("port")
        form_user = cam_record.get("username", "")
        form_pwd = decrypted_pwd
        form_path = cam_record.get("rtsp_path", "")
        form_src = cam_record.get("source", "") if form_type in ("WEBCAM", "FILE") else ""
        form_enabled = bool(cam_record["enabled"])
    else:
        form_name = ""
        form_type = "RTSP"
        form_loc = ""
        form_desc = ""
        form_ip = ""
        form_port = 554
        form_user = ""
        form_pwd = ""
        form_path = ""
        form_src = ""
        form_enabled = True

    title = "📝 Edit Camera Configuration" if mode == "edit" else "➕ Register New Surveillance Source"
    st.markdown(f"### {title}")

    # Render inputs outside Streamlit native form to allow dynamic inputs matching type selectbox
    name = st.text_input("Camera Name:", value=form_name, placeholder="e.g. Lobby Entrance Camera")
    
    types = ["RTSP", "WEBCAM", "FILE", "HTTP"]
    cam_type = st.selectbox("Connection Type:", options=types, index=types.index(form_type))

    location = st.text_input("Location / Facility Area:", value=form_loc, placeholder="e.g. Building A - Floor 2")
    description = st.text_area("Camera Description:", value=form_desc, placeholder="e.g. Surveillance over elevator bay.")

    ip_address = ""
    port = None
    username = ""
    password = ""
    rtsp_path = ""
    raw_source = ""

    if cam_type in ("RTSP", "HTTP"):
        col_ip, col_port = st.columns([3, 1])
        with col_ip:
            # Parse IP from source if editing
            raw_src = form_ip
            parsed_ip = ""
            if raw_src:
                try:
                    # Strip rtsp:// or http:// and credentials
                    clean = raw_src.split("://")[-1].split("@")[-1].split(":")[0].split("/")[0]
                    parsed_ip = clean
                except Exception:
                    parsed_ip = raw_src
            ip_address = st.text_input("IP Address / Hostname:", value=parsed_ip, placeholder="e.g. 192.168.1.100")
        
        with col_port:
            port_val = int(form_port) if form_port else (554 if cam_type == "RTSP" else 80)
            port = st.number_input("Port:", min_value=1, max_value=65535, value=port_val)

        col_user, col_pass = st.columns(2)
        with col_user:
            username = st.text_input("Username:", value=form_user, placeholder="Optional")
        with col_pass:
            password = st.text_input("Password:", value=form_pwd, type="password", placeholder="Optional")

        path_label = "RTSP Endpoint Path:" if cam_type == "RTSP" else "HTTP Endpoint Path:"
        rtsp_path = st.text_input(path_label, value=form_path, placeholder="e.g. h264/ch1/main")
    
    elif cam_type == "WEBCAM":
        raw_source = st.text_input("USB Webcam Index:", value=form_src or "0", placeholder="e.g. 0, 1")
    
    elif cam_type == "FILE":
        raw_source = st.text_input("Local Video File Path:", value=form_src, placeholder="e.g. storage/clips/sample.mp4")

    enabled = st.checkbox("Enable immediately and begin surveillance monitoring", value=form_enabled)

    # Compile data structure
    cam_data = {
        "name": name,
        "type": cam_type,
        "location": location,
        "description": description,
        "ip_address": ip_address,
        "port": port,
        "username": username,
        "password": password,
        "rtsp_path": rtsp_path,
        "source": raw_source if cam_type in ("WEBCAM", "FILE") else "",
        "enabled": enabled
    }

    # Action buttons
    col_tst, col_sv, col_cncl = st.columns(3)
    
    with col_tst:
        if st.button("Test Connection", use_container_width=True):
            with st.spinner("Testing connection by acquiring preview frame..."):
                res = gateway.camera_service.test_connection(cam_data)
                if res["success"]:
                    st.success(f"Connected successfully! Resolution: {res['resolution']} | FPS: {res['fps']:.1f}")
                    # Render live validation preview frame
                    st.image(res["frame"], channels="BGR", use_container_width=True, caption="Live Connection Test Preview Frame")
                else:
                    st.error(f"Connection Failed: {res['reason']}")

    with col_sv:
        if st.button("Save Camera", use_container_width=True, type="primary"):
            if mode == "edit":
                success, msg = gateway.camera_service.update_camera(camera_id, cam_data)
            else:
                success, msg = gateway.camera_service.register_camera(cam_data)

            if success:
                st.success(msg)
                time.sleep(1.0)
                st.session_state.camera_form_mode = None
                st.session_state.camera_to_edit = None
                st.rerun()
            else:
                st.error(msg)

    with col_cncl:
        if st.button("Cancel", use_container_width=True):
            st.session_state.camera_form_mode = None
            st.session_state.camera_to_edit = None
            st.rerun()
