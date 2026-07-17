"""Alerts page for the AERA Dashboard.

Renders filter dropdowns and dispatch logs (retry states, channels) using native Streamlit widgets.
Integrates the refactored alert_card display layout cleanly.
"""

import streamlit as st
from src.dashboard.services.backend import BackendGateway
from src.dashboard.components.alert_card import render_alert_card

def render_page(gateway: BackendGateway) -> None:
    """Render the Alert System delivery history logs page.

    Args:
        gateway: Caching backend service gateway.
    """
    # 1. Fetch alerts
    alerts = gateway.get_alerts()

    # 2. Render filter panel controls
    st.markdown("### 🔍 Filter Alerts")
    col_sev, col_status = st.columns([1, 1])

    with col_sev:
        severity_options = ["ALL", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
        selected_sev = st.selectbox("Dispatch Urgency:", severity_options)

    with col_status:
        status_options = ["ALL", "SUCCESS", "FAILED", "PENDING"]
        selected_status = st.selectbox("Delivery Status:", status_options)

    # Apply filters
    filtered_alerts = alerts
    
    if selected_sev != "ALL":
        filtered_alerts = [
            a for a in filtered_alerts 
            if a.severity.upper() == selected_sev
        ]
        
    if selected_status != "ALL":
        filtered_alerts = [
            a for a in filtered_alerts 
            if a.status.upper() == selected_status
        ]

    st.divider()

    # 3. Render Alerts List
    st.markdown(f"**Found {len(filtered_alerts)} Dispatch Records**")
    
    if filtered_alerts:
        # Loop through matched alerts
        for idx, alert in enumerate(filtered_alerts):
            # Fetch associated delivery retry logs via gateway
            history_logs = gateway.get_alert_history(alert.alert_id)
            
            # Render using the stabilized Alert Card component
            render_alert_card(alert, history_logs)
    else:
        st.info("No alert records matched current filters.")
