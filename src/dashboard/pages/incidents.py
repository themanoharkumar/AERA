"""Incidents page for the AERA Dashboard.

Renders filter panels, search options, and historical incident records.
Provides inline status updates and redirect actions using native Streamlit widgets.
"""

import streamlit as st
import datetime
from src.dashboard.services.backend import BackendGateway
from src.event.event import Event
from src.event.priority import EventPriority
from src.event.status import EventStatus
from src.event.types import EventType

def render_page(gateway: BackendGateway) -> None:
    """Render the Incidents History log page.

    Args:
        gateway: Caching backend service gateway.
    """
    # 1. Fetch incidents list
    events = gateway.get_incidents()

    # 2. Render filter panel controls
    st.markdown("### 🔍 Filter Incidents")
    col_search, col_type, col_priority, col_status = st.columns([2, 1, 1, 1])

    with col_search:
        search_query = st.text_input("Search description/camera:", placeholder="Enter keywords...")

    with col_type:
        type_options = ["ALL"] + [t.value.upper() for t in EventType]
        selected_type = st.selectbox("Category:", type_options)

    with col_priority:
        priority_options = ["ALL"] + [p.value.upper() for p in EventPriority]
        selected_priority = st.selectbox("Urgency:", priority_options)

    with col_status:
        status_options = ["ALL"] + [s.value.upper() for s in EventStatus]
        selected_status = st.selectbox("Lifecycle State:", status_options)

    # 3. Apply active filters
    filtered_events = events
    
    if search_query:
        query = search_query.lower()
        filtered_events = [
            e for e in filtered_events
            if query in e.description.lower() or query in e.camera_id.lower()
        ]
        
    if selected_type != "ALL":
        filtered_events = [
            e for e in filtered_events
            if e.event_type.value.upper() == selected_type
        ]
        
    if selected_priority != "ALL":
        filtered_events = [
            e for e in filtered_events
            if e.priority.value.upper() == selected_priority
        ]
        
    if selected_status != "ALL":
        filtered_events = [
            e for e in filtered_events
            if e.status.value.upper() == selected_status
        ]

    st.divider()

    # 4. Render Incidents List
    st.markdown(f"**Found {len(filtered_events)} Incident Records**")
    
    if filtered_events:
        # Loop through matched incidents and display each inside a bordered container card
        for idx, event in enumerate(filtered_events):
            time_str = datetime.datetime.fromtimestamp(event.timestamp).strftime("%Y-%m-%d %H:%M:%S")
            conf_pct = int(event.confidence * 100)
            
            # Map visual color tags using standard Markdown colors
            type_colors = {
                EventType.FIRE: ":red[● FIRE]",
                EventType.SMOKE: ":grey[● SMOKE]",
                EventType.VIOLENCE: ":violet[● VIOLENCE]",
                EventType.INTRUSION: ":blue[● INTRUSION]",
                EventType.CROWD: ":orange[● CROWD]",
                EventType.FALL: ":cyan[● FALL]",
            }
            type_badge = type_colors.get(event.event_type, f"● {event.event_type.value.upper()}")
            
            priority_colors = {
                EventPriority.LOW: ":green[LOW]",
                EventPriority.MEDIUM: ":orange[MEDIUM]",
                EventPriority.HIGH: ":red[HIGH]",
                EventPriority.CRITICAL: ":red[CRITICAL]",
            }
            priority_badge = priority_colors.get(event.priority, event.priority.value.upper())

            with st.container(border=True):
                # Row 1: Header tags
                col_det, col_pri = st.columns([3, 1])
                with col_det:
                    st.markdown(f"⚠️ {type_badge} | **Camera Source:** `{event.camera_id}`")
                with col_pri:
                    st.markdown(f"Urgency: {priority_badge}")
                
                # Row 2: Timestamps and Description
                st.caption(f"**Discovered:** {time_str} | **Event ID:** `{event.event_id}`")
                st.markdown(f"**Incident Details:** {event.description}")
                
                # Row 3: Confidence score progress bar
                st.caption(f"Confidence score: {conf_pct}%")
                st.progress(event.confidence)
                
                st.divider()
                
                # Row 4: Controls and status modifiers
                col_status_lbl, col_status_input, col_act_ev, col_act_rep = st.columns([2, 2, 1, 1])
                
                with col_status_lbl:
                    st.write(f"Lifecycle state: **{event.status.value.upper()}**")
                    
                with col_status_input:
                    # Dropdown selectbox allowing manual lifecycle transitions
                    current_idx = list(EventStatus).index(event.status)
                    new_status = st.selectbox(
                        "Transition status:",
                        options=list(EventStatus),
                        index=current_idx,
                        key=f"status_select_{event.event_id}",
                        format_func=lambda s: s.value.upper(),
                        label_visibility="collapsed"
                    )
                    # Automatically update backend status when selection changes
                    if new_status != event.status:
                        success, msg = gateway.update_incident_status(event.event_id, new_status)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                            
                with col_act_ev:
                    if st.button("📁 Evidence", key=f"btn_ev_{event.event_id}", use_container_width=True):
                        st.session_state.current_page = "Evidence"
                        st.session_state.selected_event_id = event.event_id
                        st.rerun()
                        
                with col_act_rep:
                    if st.button("📄 Report", key=f"btn_rep_{event.event_id}", use_container_width=True):
                        # Attempt to find if report already exists for this event
                        reports = gateway.get_reports()
                        matching_report = next((r for r in reports if r.event_id == event.event_id), None)
                        
                        st.session_state.current_page = "Reports"
                        if matching_report:
                            st.session_state.selected_report_id = matching_report.report_id
                        else:
                            st.session_state.selected_event_id = event.event_id
                        st.rerun()
    else:
        st.info("No incident records matched current filters.")
