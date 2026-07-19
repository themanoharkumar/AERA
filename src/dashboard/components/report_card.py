"""Report Card component for the AERA Dashboard.

Visualizes a summarized compiled incident report record, including timestamp,
severity levels, and interactive export/view controls using native Streamlit widgets.
"""

import streamlit as st
import datetime
import json
from dataclasses import asdict
from src.report.report import Report

def handle_view_report_details(report_id: str) -> None:
    st.session_state.current_page = "Reports"
    st.session_state.selected_report_id = report_id


def render_report_card(report: Report) -> None:
    """Render a reusable report card.

    Args:
        report: The Report dataclass instance.
    """
    # 1. Determine severity indicator styling using standard Markdown color tokens
    sev_str = report.metadata.get("severity", "LOW")
    
    severity_colors = {
        "LOW": ":green[LOW]",
        "MEDIUM": ":orange[MEDIUM]",
        "HIGH": ":red[HIGH]",
        "CRITICAL": ":red[CRITICAL]",
    }
    sev_badge = severity_colors.get(sev_str.upper(), sev_str.upper())
    
    # 2. Format timestamp
    time_str = datetime.datetime.fromtimestamp(report.timestamp).strftime("%Y-%m-%d %H:%M:%S")

    # 3. Render inside one clean container card (border=True)
    with st.container(border=True):
        col_title, col_badge = st.columns([3, 1])
        with col_title:
            st.markdown(f"📄 **{report.title}**")
        with col_badge:
            st.markdown(sev_badge)
            
        st.caption(f"**Report ID:** `{report.report_id[:8]}`")
        st.caption(f"**Compiled Time:** {time_str}")
        st.write(report.summary)

        # 4. Action Buttons (View Details, Download JSON) using columns
        col_view, col_download = st.columns([1, 1])
        
        with col_view:
            st.button(
                "View Details",
                key=f"rep_btn_view_{report.report_id}",
                on_click=handle_view_report_details,
                args=(report.report_id,),
                use_container_width=True
            )

        with col_download:
            # Convert Report dataclass to formatted JSON string
            report_json = json.dumps(asdict(report), indent=4)
            st.download_button(
                label="Download JSON",
                data=report_json,
                file_name=f"report_{report.report_id[:8]}.json",
                mime="application/json",
                key=f"rep_btn_dl_{report.report_id}",
                use_container_width=True
            )
