"""Analytics page for the AERA Dashboard.

Renders statistical distributions, camera uptimes, alert delivery successes,
and incident trend charts using native Streamlit widgets and styled Plotly charts.
"""

import streamlit as st
from src.dashboard.services.backend import BackendGateway
from src.dashboard.components.chart_widget import render_chart_widget

def render_page(gateway: BackendGateway) -> None:
    """Render the System Analytics visual insights page.

    Args:
        gateway: Caching backend service gateway.
    """
    # 1. Page Header description using caption
    st.caption("Incident distributions, alert pacing trends, and camera health performance summaries.")

    # 2. Fetch analytical dataframes from gateway
    df_trends = gateway.get_incident_trends()
    df_distribution = gateway.get_incident_distribution()
    df_alert_stats = gateway.get_alert_statistics()
    df_health = gateway.get_camera_uptime_stats()

    if df_trends.empty and df_distribution.empty and df_alert_stats.empty:
        st.info("ℹ️ **Insufficient data for analytics.** No incidents or alerts have been captured yet.")
        return

    # 3. Render Row 1: Incident Trends Line Chart & Distribution Pie Chart
    col_trends, col_dist = st.columns(2)

    with col_trends:
        render_chart_widget(
            chart_type="line",
            title="📈 Historical Incident Frequency Trends",
            data=df_trends,
            x_col="date",
            y_col="count",
            color_col="type",
            color_discrete_map={
                "fire": "#EF4444",
                "smoke": "#9CA3AF",
                "violence": "#7C3AED",
                "intrusion": "#2563EB",
                "crowd": "#F59E0B",
                "fall": "#06B6D4"
            }
        )

    with col_dist:
        render_chart_widget(
            chart_type="pie",
            title="🍕 Incident Category Distribution Shares",
            data=df_distribution,
            x_col="type",
            y_col="count",
            color_discrete_map={
                "fire": "#EF4444",
                "smoke": "#9CA3AF",
                "violence": "#7C3AED",
                "intrusion": "#2563EB",
                "crowd": "#F59E0B",
                "fall": "#06B6D4"
            }
        )

    st.write("")

    # 4. Render Row 2: Alert Success Bars & Camera Health Areas
    col_alerts, col_cameras = st.columns(2)

    with col_alerts:
        render_chart_widget(
            chart_type="bar",
            title="📊 Notification Delivery Status Breakdown",
            data=df_alert_stats,
            x_col="status",
            y_col="count",
            color_col="status",
            color_discrete_map={
                "success": "#22C55E",
                "failed": "#EF4444",
                "pending": "#F59E0B"
            }
        )

    with col_cameras:
        render_chart_widget(
            chart_type="area",
            title="📈 Camera Connection Uptime Telemetry",
            data=df_health,
            x_col="camera",
            y_col="uptime",
            color_discrete_map={"uptime": "#3B82F6"}
        )
