"""Dashboard Overview page for the AERA Dashboard.

Renders system metrics, camera counts, active incident lists, recent notifications,
and performance telemetry indicators using native Streamlit widgets.
"""

import streamlit as st
from src.dashboard.services.backend import BackendGateway
from src.dashboard.components.status_card import render_status_card
from src.dashboard.components.metric_card import render_metric_card
from src.dashboard.components.incident_card import render_incident_card
from src.camera.camera import CameraStatus

def render_page(gateway: BackendGateway) -> None:
    """Render the central system status dashboard page.

    Args:
        gateway: Caching backend service gateway.
    """
    # 1. Fetch data from backend services
    health = gateway.get_system_health()
    cameras = gateway.list_cameras()
    active_incidents = gateway.get_incidents()
    alerts = gateway.get_alerts()
    reports = gateway.get_reports()
    perf = gateway.get_performance_metrics()

    # Calculate statistics
    total_cameras = len(cameras)
    streaming_cameras = sum(1 for c in cameras if c.status == CameraStatus.STREAMING)
    
    # Active incidents: NEW or PROCESSING
    unresolved_incidents = [i for i in active_incidents if i.status.value.upper() in ("NEW", "PROCESSING")]
    active_count = len(unresolved_incidents)
    
    alert_count = len(alerts)

    # 2. Render Row 1: System Overview Cards
    col_health, col_cams, col_inc, col_alerts = st.columns(4)

    with col_health:
        is_healthy = health.get("overall_healthy", False)
        status_text = "HEALTHY" if is_healthy else "CRITICAL"
        status_color = "#22C55E" if is_healthy else "#EF4444"
        render_status_card(
            icon="🏥" if is_healthy else "🚨",
            title="System Health",
            value=status_text,
            status_color=status_color
        )

    with col_cams:
        render_status_card(
            icon="📹",
            title="Active Cameras",
            value=f"{streaming_cameras} / {total_cameras}",
            status_color="#3B82F6"
        )

    with col_inc:
        status_color = "#EF4444" if active_count > 0 else "#22C55E"
        render_status_card(
            icon="🔥",
            title="Active Incidents",
            value=active_count,
            status_color=status_color
        )

    with col_alerts:
        render_status_card(
            icon="🔔",
            title="Alerts Delivered",
            value=alert_count,
            status_color="#F59E0B"
        )

    st.write("")

    # 3. Render Row 2: Live Incidents Feed (left) & Connected Cameras (right)
    col_feed, col_cameras = st.columns([3, 2])

    with col_feed:
        st.markdown("### 🚨 Recent Incidents")
        if unresolved_incidents:
            # Display up to 3 active incidents
            for event in unresolved_incidents[:3]:
                render_incident_card(event)
        else:
            st.success("✅ **All clear.** No active incident alerts detected.")

    with col_cameras:
        st.markdown("### 📹 Connected Feeds")
        if cameras:
            for cam in cameras:
                cam_status = cam.status.value.upper()
                if cam.status == CameraStatus.STREAMING:
                    badge = "**:green[STREAMING]**"
                elif cam.status in (CameraStatus.CONNECTED, CameraStatus.CONNECTING):
                    badge = "**:blue[CONNECTED]**"
                else:
                    badge = "**:grey[OFFLINE]**"
                
                with st.container(border=True):
                    col_det, col_bdg = st.columns([3, 1])
                    with col_det:
                        st.markdown(f"📹 **{cam.name}**")
                        st.caption(f"ID: `{cam.camera_id}`")
                    with col_bdg:
                        st.markdown(badge)
        else:
            st.caption("No cameras registered in coordinate system.")

    st.write("")

    # 4. Render Row 3: Performance Telemetry Metrics
    st.markdown("### 📈 Performance Metrics")
    col_latency, col_fps, col_cpu, col_mem = st.columns(4)

    with col_latency:
        render_metric_card(
            label="Integration Latency",
            value=f"{perf.get('latency_total', 3.95):.2f}",
            unit="ms",
            sublabel="Target: <15.0ms",
            color_accent="#22C55E"
        )

    with col_fps:
        render_metric_card(
            label="Processing Throughput",
            value=f"{perf.get('fps', 30.0):.1f}",
            unit="FPS",
            sublabel="Real-time capture paced",
            color_accent="#3B82F6"
        )

    with col_cpu:
        render_metric_card(
            label="System CPU Load",
            value=f"{perf.get('cpu_usage', 0.5):.1f}",
            unit="%",
            sublabel="Multi-threaded processing",
            color_accent="#F59E0B"
        )

    with col_mem:
        render_metric_card(
            label="Process Memory RSS",
            value=f"{perf.get('memory_usage', 52.0):.1f}",
            unit="MB",
            sublabel="Peak heap stabilized",
            color_accent="#E5E7EB"
        )
