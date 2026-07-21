"""Reports page for the AERA Dashboard.

Renders compiled incident summaries, export capabilities, and report generation triggers.
Corrects model fields and uses 100% native Streamlit components.
"""

import streamlit as st
import datetime
from src.dashboard.services.backend import BackendGateway
from src.report.report import Report

def render_page(gateway: BackendGateway) -> None:
    """Render the Incident Reports page.

    Args:
        gateway: Caching backend service gateway.
    """
    # 1. Fetch reports list
    reports = gateway.get_reports()

    # 2. Check if a specific report redirect or generation trigger is set in state
    redirect_report_id = st.session_state.get("selected_report_id")
    redirect_event_id = st.session_state.get("selected_event_id")

    selected_idx = 0
    if redirect_report_id:
        for idx, rep in enumerate(reports):
            if rep.report_id == redirect_report_id:
                selected_idx = idx
                break
        st.session_state.selected_report_id = None
        
    elif redirect_event_id:
        # Prompt option to generate a new report
        st.info(f"📄 No report compiled yet for Event `{redirect_event_id[:8]}`.")
        if st.button("🔧 Generate Incident Report Now", type="primary", use_container_width=True):
            with st.spinner("Compiling incident datasets..."):
                success, result = gateway.create_report_for_event(redirect_event_id)
                if success:
                    st.success("Report successfully compiled!")
                    st.session_state.selected_report_id = result.report_id
                    st.session_state.selected_event_id = None
                    st.rerun()
                else:
                    st.error(f"Failed to generate report: {result}")
        st.divider()

    if not reports:
        st.info("ℹ️ **No reports have been generated.**")
        return

    # 3. Create selector selectbox
    st.markdown("### 📄 Select Incident Report")
    
    def format_rep_label(rep: Report) -> str:
        time_str = datetime.datetime.fromtimestamp(rep.timestamp).strftime("%H:%M:%S")
        return f"{rep.title} ({time_str})"
        
    active_report = st.selectbox(
        "Choose a report:",
        reports,
        index=selected_idx,
        format_func=format_rep_label,
        label_visibility="collapsed"
    )

    st.divider()

    if active_report:
        # 4. Render Master-Detail split layout (Metadata on left, Markdown Preview on right)
        col_meta, col_preview = st.columns([2, 3])

        with col_meta:
            st.markdown("### 📝 Details")
            
            # Map severity colored tags using standard Markdown colors
            sev_str = active_report.metadata.get("severity", "LOW")
            severity_colors = {
                "LOW": ":green[LOW]",
                "MEDIUM": ":orange[MEDIUM]",
                "HIGH": ":red[HIGH]",
                "CRITICAL": ":red[CRITICAL]",
            }
            sev_badge = severity_colors.get(sev_str.upper(), sev_str.upper())

            with st.container(border=True):
                st.write(f"**Report ID:** `{active_report.report_id}`")
                st.write(f"**Event ID:** `{active_report.event_id}`")
                st.write(f"**Decision ID:** `{active_report.decision_id}`")
                st.write(f"**Evidence Package ID:** `{active_report.evidence_id}`")
                
                time_str = datetime.datetime.fromtimestamp(active_report.timestamp).strftime("%Y-%m-%d %H:%M:%S")
                st.write(f"**Compiled Time:** {time_str}")
                st.write(f"**Urgency Level:** {sev_badge}")
                
            st.write("")
            
            # Download actions
            st.markdown("##### 📥 Export Document")
            
            # Download Markdown file (.md)
            # Corrected to use active_report.summary (matches backend model)
            st.download_button(
                label="Download Markdown Document (.md)",
                data=active_report.summary,
                file_name=f"report_{active_report.report_id[:8]}.md",
                mime="text/markdown",
                use_container_width=True,
                key="btn_dl_md_file"
            )

        with col_preview:
            st.markdown("### 🔍 Document Preview")
            with st.container(border=True):
                # Toggle view between Operator Report and Technical Forensic Report
                view_tech = st.toggle("View Technical Report", value=False, key=f"toggle_tech_{active_report.report_id}")
                if view_tech:
                    st.markdown(active_report.summary)
                else:
                    st.code(active_report.operator_summary or active_report.summary, language="text")
