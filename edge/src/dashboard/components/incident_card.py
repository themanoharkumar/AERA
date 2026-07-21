"""Incident Card component for the AERA Dashboard.

Visualizes a single detected emergency incident (event), rendering status indicators,
severity badges, and confidence metrics using native Streamlit widgets.
"""

import streamlit as st
import datetime
from src.event.event import Event
from src.event.priority import EventPriority
from src.event.types import EventType

def handle_view_evidence(event_id: str) -> None:
    st.session_state.current_page = "Evidence"
    st.session_state.selected_event_id = event_id


def render_incident_card(incident) -> None:
    """Render a reusable incident card.

    Args:
        incident: The Incident instance.
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
    
    hazard_badges = []
    for hz in getattr(incident, "observed_hazards", [incident.incident_type]):
        badge = type_colors.get(hz, f"● {hz.value.upper()}")
        hazard_badges.append(badge)
    type_badge = " | ".join(hazard_badges)

    # 2. Map priority/severity status colors
    severity_colors = {
        EventPriority.LOW: ":green[LOW]",
        EventPriority.MEDIUM: ":orange[MEDIUM]",
        EventPriority.HIGH: ":red[HIGH]",
        EventPriority.CRITICAL: ":red[CRITICAL]",
    }
    sev_badge = severity_colors.get(incident.priority, incident.priority.value.upper())

    # 3. Format timestamps
    start_str = datetime.datetime.fromtimestamp(incident.start_time).strftime("%H:%M:%S")
    last_str = datetime.datetime.fromtimestamp(incident.last_seen_time).strftime("%H:%M:%S")

    # 4. Confidence progress bar value
    conf_pct = int(incident.confidence * 100)

    # 5. Render inside one clean container card (border=True)
    with st.container(border=True):
        col_content, col_thumb = st.columns([3, 1])
        
        with col_content:
            col_header, col_badge = st.columns([3, 1])
            with col_header:
                st.markdown(f"⚠️ {type_badge} Detected")
            with col_badge:
                st.markdown(sev_badge)
                
            st.caption(f"**Camera Source:** {incident.camera_id}")
            st.caption(f"**Discovered:** {start_str} | **Last Seen:** {last_str}")
            st.caption(f"**Duration:** {incident.duration:.1f}s | **Detections count:** {incident.detection_count}")
            st.markdown(f"**Description:** {incident.description}")
            
            # Confidence Bar
            st.caption(f"Latest Confidence score: {conf_pct}%")
            st.progress(incident.confidence)
 
            # Footer Details and Action Redirect Button
            col_meta, col_btn = st.columns([3, 2])
            with col_meta:
                st.caption(f"ID: `{incident.incident_id[:8]}`")
                st.caption(f"Status: **{incident.status.value.upper()}**")
            with col_btn:
                st.button(
                    "View Evidence",
                    key=f"inc_action_view_{incident.incident_id}",
                    on_click=handle_view_evidence,
                    args=(incident.incident_id,),
                    use_container_width=True
                )

        with col_thumb:
            if getattr(incident, "evidence_list", []):
                import os
                first_ev = incident.evidence_list[0]
                ev_dir = os.path.dirname(first_ev.image_path)
                latest_path = os.path.join(ev_dir, "latest.jpg")
                image_to_show = latest_path if os.path.exists(latest_path) else first_ev.image_path
                
                if os.path.exists(image_to_show):
                    st.image(image_to_show, caption="Latest Frame", use_container_width=True)
                else:
                    st.caption("No thumbnail file")
            else:
                st.caption("No evidence captured")
