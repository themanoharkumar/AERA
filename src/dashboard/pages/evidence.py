"""Evidence page for the AERA Dashboard.

Renders screenshot viewer panels, video file references, and structured metadata
payload inspect blocks using native Streamlit widgets.
"""

import streamlit as st
import datetime
import json
import os
from src.dashboard.services.backend import BackendGateway
from src.evidence.evidence import Evidence

def render_page(gateway: BackendGateway) -> None:
    """Render the Evidence Viewer analysis page.

    Args:
        gateway: Caching backend service gateway.
    """
    # 1. Fetch evidence packages
    evidence_list = gateway.get_evidence()

    # 2. Check if selected package redirect was set in session state
    selected_idx = 0
    redirect_event_id = st.session_state.get("selected_event_id")
    
    if redirect_event_id:
        # Find matching package index
        for idx, ev in enumerate(evidence_list):
            if ev.event_id == redirect_event_id:
                selected_idx = idx
                break
        # Clear redirect from state
        st.session_state.selected_event_id = None

    if not evidence_list:
        st.warning("📁 **No evidence packages** generated yet.")
        return

    # 3. Create selector selectbox
    st.markdown("### 📁 Select Evidence Package")
    
    # Format labels displaying ID and type details
    def format_ev_label(ev: Evidence) -> str:
        time_str = datetime.datetime.fromtimestamp(ev.timestamp).strftime("%H:%M:%S")
        detector = ev.metadata.get("detector_name", "AI")
        return f"Package {ev.evidence_id[:8]} ({time_str} - {detector})"
        
    selected_evidence = st.selectbox(
        "Choose an evidence package:",
        evidence_list,
        index=selected_idx,
        format_func=format_ev_label,
        label_visibility="collapsed"
    )

    st.divider()

    if selected_evidence:
        # 4. Create Master-Detail splits (Media on left, Metadata on right)
        col_media, col_metadata = st.columns([5, 4])

        with col_media:
            st.markdown("### 🖼️ Preserved Media")
            
            # Display image screenshot
            img_path = selected_evidence.image_path
            
            if img_path and os.path.exists(img_path):
                st.image(img_path, caption="Verified Incident Frame Screenshot", use_container_width=True)
            else:
                st.warning(f"⚠️ Screenshot file not found at: `{img_path}`")
                
            # Render video path information block
            st.markdown("##### 📹 Associated Video Reference")
            with st.container(border=True):
                st.markdown(f"**Physical File Path:**")
                st.code(selected_evidence.video_path, language="bash")
                st.caption("Video streaming server streaming support is planned for Phase 10.")

        with col_metadata:
            st.markdown("### 📝 Structured Details")
            
            with st.container(border=True):
                st.caption("IDENTITY RELATIONSHIPS")
                st.write(f"**Evidence Package ID:** `{selected_evidence.evidence_id}`")
                st.write(f"**Evaluated Event ID:** `{selected_evidence.event_id}`")
                st.write(f"**Decision Reasoning ID:** `{selected_evidence.decision_id}`")
                
                time_str = datetime.datetime.fromtimestamp(selected_evidence.timestamp).strftime("%Y-%m-%d %H:%M:%S")
                st.write(f"**Capture Timestamp:** {time_str}")

            st.write("")
            
            # Interactive JSON meta payload viewer
            st.markdown("##### 📊 Telemetry Metadata JSON Payload")
            st.json(selected_evidence.metadata)
