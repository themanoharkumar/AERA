"""Status Card component for the AERA Dashboard.

Visualizes a single system statistic card using native Streamlit containers and columns,
satisfying the minimal visual weight requirements.
"""

import streamlit as st
from typing import Any

def render_status_card(
    icon: str,
    title: str,
    value: Any,
    status_color: str = "#3B82F6"
) -> None:
    """Render a reusable status statistic card.

    Args:
        icon: Emoji/symbol associated with the metric.
        title: Descriptive label of the statistic.
        value: Numeric count or string data to display.
        status_color: Visual accent status color (ignored to reduce visual weight).
    """
    with st.container(border=True):
        col_text, col_icon = st.columns([4, 1])
        with col_text:
            st.caption(title.upper())
            st.markdown(f"### **{value}**")
        with col_icon:
            st.write(icon)
