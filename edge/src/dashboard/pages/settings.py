"""Settings page for the AERA Dashboard.

Renders configurations, thresholds, notification schedules, and includes
the pipeline simulator widget using native Streamlit inputs and control triggers.
"""

import streamlit as st
from src.dashboard.services.backend import BackendGateway
from src.camera.camera import CameraStatus

def render_page(gateway: BackendGateway) -> None:
    """Render system settings and pipelines simulation controls page.

    Args:
        gateway: Caching backend service gateway.
    """
    # 1. Page Header description
    st.caption("Configure detection parameters, delivery endpoints, and simulate pipelines emergency states.")

    # 2. Render Page Tabs (General Configurations, Simulation Controls)
    tab_simulator, tab_configs = st.tabs(["🧪 Event Simulator Pipeline", "⚙️ Configuration Parameters"])

    with tab_simulator:
        st.markdown("### 🧪 Emergency Pipeline Frame Simulator")
        
        # Native alert box replacing raw HTML simulator warning panel
        st.info(
            "Simulate emergency situations by feeding incident frames (fire, smoke, normal) "
            "to streaming cameras. This validates pipeline data propagation from detectors "
            "up to delivered alerts."
        )

        # Simulator input options
        cameras = gateway.list_cameras()
        streaming_cams = [c for c in cameras if c.status == CameraStatus.STREAMING]

        if not streaming_cams:
            st.warning("⚠️ No active streaming feeds available. Start a camera first on the Live Cameras page.")
            return

        col_cam, col_frame = st.columns(2)
        
        with col_cam:
            selected_cam = st.selectbox(
                "Target Camera Feed:",
                streaming_cams,
                format_func=lambda c: c.name
            )

        with col_frame:
            frame_options = ["fire", "smoke", "normal"]
            selected_frame = st.selectbox("Frame Template to Inject:", frame_options)

        st.divider()

        # Trigger injection event
        if st.button("🚀 Inject Frame Template & Trigger Pipeline", type="primary", use_container_width=True):
            with st.spinner("Injecting frame buffers..."):
                success, msg = gateway.simulate_frame_injection(selected_cam.camera_id, selected_frame)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

    with tab_configs:
        st.markdown("### ⚙️ System Configuration Parameters")

        # 1. Fetch active thresholds configuration from the gateway
        config_data = gateway.export_configuration()
        fire_thresh = config_data.get("detector_fire_detector", {}).get("confidence_threshold", 0.50)
        smoke_thresh = config_data.get("detector_smoke_detector", {}).get("confidence_threshold", 0.45)

        # Threshold parameters inputs
        st.markdown("##### 🎯 Detection Confidence Thresholds")
        col_fire_th, col_smoke_th = st.columns(2)
        
        with col_fire_th:
            fire_val = st.slider("Fire Event Confidence limit:", min_value=0.0, max_value=1.0, value=fire_thresh, step=0.05)
        with col_smoke_th:
            smoke_val = st.slider("Smoke Event Confidence limit:", min_value=0.0, max_value=1.0, value=smoke_thresh, step=0.05)

        st.divider()

        # Notification target configurations
        st.markdown("##### 📢 Delivery Endpoints & Integrations")
        st.text_input("Emergency Operations Email Endpoint:", value="dispatch@city-emergency.org")
        st.text_input("Telegram Incident Operations Channel Username:", value="@AERA_Incident_Ops")

        st.divider()

        # Camera registry administration details
        st.markdown("##### 📹 Registered Cameras Registry")
        for cam in cameras:
            with st.container(border=True):
                col_c_name, col_c_source = st.columns([2, 1])
                with col_c_name:
                    st.markdown(f"📹 **{cam.name}**")
                    st.caption(f"ID: `{cam.camera_id}` | State: **{cam.status.value.upper()}**")
                with col_c_source:
                    st.markdown("**Source URI/Index:**")
                    st.code(str(cam.source))

        st.divider()

        # Action Control Triggers
        col_save, col_reset = st.columns([1, 1])
        with col_save:
            if st.button("💾 Save Configs Changes", use_container_width=True, type="primary"):
                with st.spinner("Saving configuration settings..."):
                    success_fire, msg_fire = gateway.update_threshold("fire_detector", fire_val)
                    success_smoke, msg_smoke = gateway.update_threshold("smoke_detector", smoke_val)
                    gateway.reload_models()
                    if success_fire and success_smoke:
                        st.success("Configurations successfully synchronized and persisted.")
                    else:
                        st.error(f"Failed to synchronize thresholds: {msg_fire} | {msg_smoke}")
        with col_reset:
            if st.button("🔄 Restore Engine Defaults", use_container_width=True):
                with st.spinner("Restoring default engine settings..."):
                    success, msg = gateway.reset_pipeline()
                    if success:
                        st.success("System settings returned to defaults.")
                        st.rerun()
                    else:
                        st.error(f"Failed to restore defaults: {msg}")
