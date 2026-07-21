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
    from src.incident.incident import IncidentState

    # 1. Fetch data from backend services
    health = gateway.get_system_health()
    cameras = gateway.list_cameras()
    all_incidents = gateway.get_incidents()
    alerts = gateway.get_alerts()
    reports = gateway.get_reports()
    perf = gateway.get_performance_metrics()

    # Calculate statistics
    total_cameras = len(cameras)
    streaming_cameras = sum(1 for c in cameras if c.status == CameraStatus.STREAMING)
    
    # Active incidents: NEW, ACTIVE, UPDATED
    active_incidents_list = [
        i for i in all_incidents 
        if i._status in (IncidentState.NEW, IncidentState.ACTIVE, IncidentState.UPDATED)
    ]
    active_count = len(active_incidents_list)

    # Resolved incidents: RESOLVED
    resolved_incidents_list = [
        i for i in all_incidents 
        if i._status == IncidentState.RESOLVED
    ]
    resolved_count = len(resolved_incidents_list)
    
    alert_count = len(alerts)

    # 2. Render Row 1: System Overview Cards
    col_health, col_cams, col_inc, col_resolved, col_alerts = st.columns(5)

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

    with col_resolved:
        render_status_card(
            icon="✅",
            title="Resolved Incidents",
            value=resolved_count,
            status_color="#22C55E"
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
        recent_incidents = sorted(all_incidents, key=lambda x: x.start_time, reverse=True)[:5]
        if recent_incidents:
            for event in recent_incidents:
                render_incident_card(event)
        else:
            st.info("ℹ️ **No incidents detected.** System operating normally.")

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
        threads = int(perf.get('thread_count', 0))
        render_metric_card(
            label="Processing Throughput",
            value=f"{perf.get('fps', 0.0):.1f}",
            unit="FPS",
            sublabel=f"Active Threads: {threads}",
            color_accent="#3B82F6"
        )

    with col_cpu:
        uptime_secs = int(perf.get('uptime', 0))
        uptime_str = f"{uptime_secs // 60}m {uptime_secs % 60}s" if uptime_secs >= 60 else f"{uptime_secs}s"
        render_metric_card(
            label="System CPU Load",
            value=f"{perf.get('cpu_usage', 0.0):.1f}",
            unit="%",
            sublabel=f"Process Uptime: {uptime_str}",
            color_accent="#F59E0B"
        )

    with col_mem:
        mem_pct = perf.get('memory_percent', 0.0)
        render_metric_card(
            label="Process Memory RSS",
            value=f"{perf.get('memory_usage', 0.0):.1f}",
            unit="MB",
            sublabel=f"Memory Percent: {mem_pct:.2f}%",
            color_accent="#E5E7EB"
        )

    # 5. Auto-refresh overview page
    import os
    if os.environ.get("STREAMLIT_NO_REFRESH", "false").lower() != "true":
        import time
        time.sleep(3.0)
        st.rerun()
