"""Alert Card component for the AERA Dashboard.

Visualizes a single dispatched alert notification, showing delivery channels,
severities, retry history lists, and statuses using native Streamlit widgets.
"""

import streamlit as st
import datetime
from typing import List, Any
from src.alert.alert import Alert

def render_alert_card(alert: Alert, history_logs: List[Any] = None) -> None:
    """Render a reusable alert status card.

    Args:
        alert: The Alert dataclass instance.
        history_logs: Optional list of HistoryRecord logs for this alert.
    """
    # 1. Map severity indicator styling using standard Markdown color tokens
    sev_str = alert.severity
    severity_colors = {
        "LOW": ":green[LOW]",
        "MEDIUM": ":orange[MEDIUM]",
        "HIGH": ":red[HIGH]",
        "CRITICAL": ":red[CRITICAL]",
    }
    sev_badge = severity_colors.get(sev_str.upper(), sev_str.upper())

    # 2. Map status colors (Success: Green, Failed: Red, Pending/Warning: Yellow)
    status_str = alert.status.upper()
    if status_str == "SUCCESS":
        status_badge = "**:green[● SUCCESS]**"
    elif status_str == "FAILED":
        status_badge = "**:red[● FAILED]**"
    else:
        status_badge = "**:orange[● PENDING]**"

    # 3. Format timestamp
    time_str = datetime.datetime.fromtimestamp(alert.timestamp).strftime("%Y-%m-%d %H:%M:%S")

    # 4. Render inside one clean container card (border=True)
    with st.container(border=True):
        col_title, col_badge = st.columns([3, 1])
        with col_title:
            st.markdown("🔔 **Alert Dispatched**")
        with col_badge:
            st.markdown(sev_badge)
            
        st.caption(f"**Alert ID:** `{alert.alert_id[:8]}`")
        st.caption(f"**Report ID:** `{alert.report_id[:8]}`")
        st.caption(f"**Dispatch Time:** {time_str}")

        st.divider()

        col_status_lbl, col_status_val = st.columns([2, 1])
        with col_status_lbl:
            st.write("Delivery Status:")
        with col_status_val:
            st.markdown(status_badge)

        # 5. Expandable Delivery logs (Retries, Channels)
        if history_logs:
            with st.expander("👁️ View Dispatch Logs & Pacing Retries"):
                for idx, log in enumerate(history_logs, start=1):
                    # Use log.delivery_timestamp to match backend HistoryRecord model
                    log_time = datetime.datetime.fromtimestamp(log.delivery_timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    log_status = log.delivery_status.upper()
                    log_color = ":green[SUCCESS]" if log_status == "SUCCESS" else ":red[FAILED]"
                    
                    with st.container(border=True):
                        st.caption(f"**Attempt #{idx}:** {log_time}")
                        st.markdown(f"Channel: **{log.notification_channel}**")
                        st.markdown(f"Status: {log_color} (Retry: {log.retry_count})")
        else:
            st.caption("No retry logs recorded.")
