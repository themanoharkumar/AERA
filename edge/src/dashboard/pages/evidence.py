"""Evidence page for the AERA Dashboard.

Renders screenshot viewer panels, video file references, and structured metadata
payload inspect blocks using native Streamlit widgets.
"""

import streamlit as st
import datetime
import json
import os
import pandas as pd
from src.dashboard.services.backend import BackendGateway

def render_page(gateway: BackendGateway) -> None:
    """Render the Evidence Viewer analysis page.

    Args:
        gateway: Caching backend service gateway.
    """
    # 1. Fetch incidents
    incident_list = gateway.get_incidents()

    # 2. Check if selected package redirect was set in session state
    selected_idx = 0
    redirect_event_id = st.session_state.get("selected_event_id")
    
    if redirect_event_id:
        # Find matching incident index
        for idx, inc in enumerate(incident_list):
            if inc.incident_id == redirect_event_id:
                selected_idx = idx
                break
        # Clear redirect from state
        st.session_state.selected_event_id = None

    if not incident_list:
        st.info("ℹ️ **No incidents available.** No evidence packages have been captured yet.")
        return

    # 3. Create selector selectbox
    st.markdown("### 📁 Select Incident Evidence Collection")
    
    def format_inc_label(inc) -> str:
        time_str = datetime.datetime.fromtimestamp(inc.start_time).strftime("%H:%M:%S")
        return f"Incident {inc.incident_id[:8]} ({time_str} - {inc.incident_type.value} on {inc.camera_id})"
        
    selected_incident = st.selectbox(
        "Choose an incident:",
        incident_list,
        index=selected_idx,
        format_func=format_inc_label,
        label_visibility="collapsed"
    )

    st.divider()

    if selected_incident:
        # Get evidence folder path from first evidence package
        first_ev = selected_incident.evidence_list[0] if selected_incident.evidence_list else None
        ev_dir = os.path.dirname(first_ev.image_path) if first_ev else None
        
        # 4. Create Master-Detail splits (Media on left, Metadata on right)
        col_media, col_metadata = st.columns([5, 4])

        with col_media:
            st.markdown("### 🖼️ Preserved Media Collection")
            
            tab_latest, tab_original, tab_initial, tab_snapshots = st.tabs([
                "📷 Latest Annotated", 
                "🖼️ Original Frame", 
                "🕒 Initial Annotated",
                "🎞️ Snapshots History"
            ])
            
            with tab_latest:
                latest_path = os.path.join(ev_dir, "latest.jpg") if ev_dir else None
                if latest_path and os.path.exists(latest_path):
                    st.image(latest_path, caption="Latest Annotated Incident Frame", use_container_width=True)
                elif first_ev and os.path.exists(first_ev.image_path):
                    st.image(first_ev.image_path, caption="Initial Annotated Incident Frame", use_container_width=True)
                else:
                    st.warning("No latest annotated image available.")
                    
            with tab_original:
                orig_path = os.path.join(ev_dir, "original.jpg") if ev_dir else None
                if orig_path and os.path.exists(orig_path):
                    st.image(orig_path, caption="Prinstine Original Frame", use_container_width=True)
                else:
                    st.warning("No original image available.")
                    
            with tab_initial:
                if first_ev and os.path.exists(first_ev.image_path):
                    st.image(first_ev.image_path, caption="Initial Annotated Incident Frame", use_container_width=True)
                else:
                    st.warning("No initial annotated image available.")
                    
            with tab_snapshots:
                if ev_dir and os.path.exists(ev_dir):
                    snapshots = sorted([f for f in os.listdir(ev_dir) if f.startswith("snapshot_")])
                    if snapshots:
                        selected_snap = st.selectbox("Select historical snapshot:", snapshots)
                        if selected_snap:
                            snap_path = os.path.join(ev_dir, selected_snap)
                            st.image(snap_path, caption=f"Snapshot: {selected_snap}", use_container_width=True)
                    else:
                        st.info("No historical snapshots saved for this incident.")
                else:
                    st.warning("Evidence folder not found.")
                
            # Render video path information block
            st.markdown("##### 📹 Associated Video Reference")
            with st.container(border=True):
                st.markdown(f"**Physical File Path:**")
                st.code(first_ev.video_path if first_ev else "No video recorded", language="bash")
                st.caption("Video streaming server streaming support is planned for Phase 10.")

        with col_metadata:
            st.markdown("### 📝 Structured Incident Details")
            
            with st.container(border=True):
                st.caption("IDENTITY & STATE RELATIONSHIPS")
                st.write(f"**Incident ID:** `{selected_incident.incident_id}`")
                st.write(f"**Camera source:** `{selected_incident.camera_id}`")
                st.write(f"**Observed hazards:** `{', '.join([h.value for h in getattr(selected_incident, 'observed_hazards', [])])}`")
                st.write(f"**Urgency level:** `{selected_incident.priority.value.upper()}`")
                st.write(f"**Current lifecycle status:** **{selected_incident.status.value.upper()}**")
                st.write(f"**Active duration:** {selected_incident.duration:.1f}s")
                st.write(f"**Detections count:** {selected_incident.detection_count}")
                st.write(f"**Latest Confidence:** {selected_incident.confidence:.1%}")
                
            # Incident Timeline Display
            st.markdown("##### 🕒 Detection Timeline History")
            if selected_incident.timeline:
                timeline_df = pd.DataFrame([
                    {
                        "Time": datetime.datetime.fromtimestamp(t["timestamp"]).strftime("%H:%M:%S"),
                        "Event Description": t["event"],
                        "Confidence": f"{t['confidence']:.1%}",
                        "BBox": str(t["bounding_box"])
                    } for t in selected_incident.timeline
                ])
                st.dataframe(timeline_df, use_container_width=True, hide_index=True)
            else:
                st.info("No timeline events recorded.")
            
            # Interactive JSON meta payload viewer
            st.markdown("##### 📊 Latest Evidence JSON Payload")
            if first_ev:
                st.json(first_ev.metadata)
            else:
                st.info("No telemetry metadata payload available.")
