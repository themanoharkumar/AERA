"""Incident Card component for the AERA Dashboard.

Visualizes a single detected emergency incident (event), rendering status indicators,
severity badges, and confidence metrics using native Streamlit widgets.
"""

import streamlit as st
import datetime
from src.event.event import Event
from src.event.priority import EventPriority
from src.event.types import EventType

def render_incident_card(event: Event) -> None:
    """Render a reusable incident event card.

    Args:
        event: The Event dataclass instance.
    """
    # 1. Map incident type colors using standard Markdown color tokens
    type_colors = {
        EventType.FIRE: ":red[● FIRE]",
        EventType.SMOKE: ":grey[● SMOKE]",
        EventType.VIOLENCE: ":violet[● VIOLENCE]",
        EventType.INTRUSION: ":blue[● INTRUSION]",
        EventType.CROWD: ":orange[● CROWD]",
        EventType.FALL: ":cyan[● FALL]",
    }
    type_badge = type_colors.get(event.event_type, f"● {event.event_type.value.upper()}")

    # 2. Map priority/severity status colors
    severity_colors = {
        EventPriority.LOW: ":green[LOW]",
        EventPriority.MEDIUM: ":orange[MEDIUM]",
        EventPriority.HIGH: ":red[HIGH]",
        EventPriority.CRITICAL: ":red[CRITICAL]",
    }
    sev_badge = severity_colors.get(event.priority, event.priority.value.upper())

    # 3. Format timestamp
    time_str = datetime.datetime.fromtimestamp(event.timestamp).strftime("%Y-%m-%d %H:%M:%S")

    # 4. Confidence progress bar value
    conf_pct = int(event.confidence * 100)

    # 5. Render inside one clean container card (border=True)
    with st.container(border=True):
        col_header, col_badge = st.columns([3, 1])
        with col_header:
            st.markdown(f"⚠️ {type_badge} Detected")
        with col_badge:
            st.markdown(sev_badge)
            
        st.caption(f"**Camera Source:** {event.camera_id}")
        st.caption(f"**Time:** {time_str}")
        st.markdown(f"**Description:** {event.description}")

        # Confidence Bar
        st.caption(f"Confidence score: {conf_pct}%")
        st.progress(event.confidence)

        # Footer Details and Action Redirect Button
        col_meta, col_btn = st.columns([3, 2])
        with col_meta:
            st.caption(f"ID: `{event.event_id[:8]}`")
            st.caption(f"Status: **{event.status.value.upper()}**")
        with col_btn:
            if st.button("View Evidence", key=f"inc_action_view_{event.event_id}", use_container_width=True):
                st.session_state.current_page = "Evidence"
                st.session_state.selected_event_id = event.event_id
                st.rerun()
