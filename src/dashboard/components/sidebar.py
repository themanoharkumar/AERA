"""Sidebar navigation component for the AERA Dashboard.

Handles page switching and displays global branding in the sidebar using native Streamlit widgets.
"""

import streamlit as st

def handle_sidebar_nav(page_name: str) -> None:
    st.session_state.current_page = page_name


def render_sidebar() -> None:
    """Render the navigation panel inside the Streamlit sidebar."""
    with st.sidebar:
        # 1. Branding Header
        st.subheader("🚨 AERA")
        st.caption("Command Center v2.0")
        st.divider()

        # 2. Navigation items
        nav_items = [
            ("Dashboard", "📊"),
            ("Live Cameras", "📹"),
            ("Incidents", "🚨"),
            ("Evidence", "📁"),
            ("Reports", "📄"),
            ("Alerts", "🔔"),
            ("Analytics", "📈"),
            ("Settings", "⚙"),
        ]

        st.caption("NAVIGATION")

        for page_name, icon in nav_items:
            is_active = (st.session_state.current_page == page_name)
            
            # Using Streamlit native buttons to trigger reruns on state change
            # Active button uses 'primary' styling (accent color), inactive uses 'secondary'
            st.button(
                f"{icon}  {page_name}",
                key=f"nav_btn_{page_name.lower().replace(' ', '_')}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
                on_click=handle_sidebar_nav,
                args=(page_name,)
            )

        # 3. Footer branding info
        st.divider()
        st.caption("SAIF-Compliant System")
        st.caption("Security & AI Safety Framework")
