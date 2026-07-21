"""Metric Card component for the AERA Dashboard.

Visualizes performance parameters using standard layout and native Streamlit widgets.
"""

import streamlit as st
from typing import Any, Optional

def render_metric_card(
    label: str,
    value: Any,
    unit: str = "",
    sublabel: Optional[str] = None,
    color_accent: str = "#E5E7EB"
) -> None:
    """Render a reusable performance metric card.

    Args:
        label: Performance label (e.g. 'Latency', 'CPU Usage').
        value: Numerical value.
        unit: Optional unit suffix (e.g. 'ms', '%', 'MB').
        sublabel: Optional status subtext (e.g. '+2% since boot').
        color_accent: Ignored to reduce visual weight.
    """
    with st.container(border=True):
        st.caption(label.upper())
        val_str = f"{value} {unit}" if unit else str(value)
        st.markdown(f"### **{val_str}**")
        if sublabel:
            st.caption(sublabel)
