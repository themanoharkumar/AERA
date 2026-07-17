"""Top Navbar component for the AERA Dashboard.

Displays active page title, real-time system status indicators, current local time,
and provides manual layout refreshes using native Streamlit widgets.
"""

import streamlit as st
import datetime
from src.dashboard.services.backend import BackendGateway

def render_navbar(gateway: BackendGateway) -> None:
    """Render the top navigation bar component.

    Args:
        gateway: Caching backend service gateway.
    """
    # 1. Fetch system health metrics from gateway
    health = gateway.get_system_health()
    is_healthy = health.get("overall_healthy", False)
    
    # Healthy: Green, Critical: Red
    status_indicator = "**:green[● HEALTHY]**" if is_healthy else "**:red[● CRITICAL]**"

    # 2. Get formatted current local timestamp
    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 3. Create responsive top navbar header grid (Title, Health Badge, Time, Refresh Button)
    col_title, col_status, col_time, col_refresh = st.columns([3, 2, 2, 1])

    with col_title:
        st.subheader(f"🚨 AERA / {st.session_state.current_page}")

    with col_status:
        # Vertical centering using empty space or vertical container is handled by columns,
        # simply printing markdown displays cleanly.
        st.markdown(f"**System Status:** {status_indicator}")

    with col_time:
        st.markdown(f"**Local Time:** `{current_time_str}`")

    with col_refresh:
        # Refresh button that triggers Streamlit page rerun
        if st.button("🔄 Refresh", key="navbar_refresh_btn", use_container_width=True):
            st.rerun()

    # 4. Draw horizontal layout separator line
    st.divider()
