"""Plotly Chart Widget component for the AERA Dashboard.

Standardizes data visualization charts (lines, bars, pies, areas) styled
using custom light theme variables and transparent layouts using native Streamlit.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Any, Dict, List, Optional

def render_chart_widget(
    chart_type: str,
    title: str,
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: Optional[str] = None,
    color_discrete_map: Optional[Dict[str, str]] = None
) -> None:
    """Render a reusable Plotly chart styled with the AERA light theme.

    Args:
        chart_type: The layout type (e.g. 'line', 'bar', 'pie', 'area').
        title: Chart heading.
        data: Pandas DataFrame containing the dataset.
        x_col: DataFrame column for horizontal x-axis values.
        y_col: DataFrame column for vertical y-axis values.
        color_col: Optional column name for color differentiation.
        color_discrete_map: Custom hex value map matching system specifications.
    """
    with st.container(border=True):
        st.markdown(f"##### {title}")
        
        if data.empty:
            st.info("No historical telemetry records available.")
            return

        # 1. Generate core Plotly figure based on type
        if chart_type.lower() == "line":
            fig = px.line(
                data, x=x_col, y=y_col, color=color_col,
                color_discrete_map=color_discrete_map
            )
            # Smooth line curves
            fig.update_traces(line=dict(width=3))
        elif chart_type.lower() == "bar":
            fig = px.bar(
                data, x=x_col, y=y_col, color=color_col,
                color_discrete_map=color_discrete_map
            )
        elif chart_type.lower() == "area":
            fig = px.area(
                data, x=x_col, y=y_col, color=color_col,
                color_discrete_map=color_discrete_map
            )
        elif chart_type.lower() == "pie":
            fig = px.pie(
                data, names=x_col, values=y_col,
                color_discrete_map=color_discrete_map
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
        else:
            st.error(f"Unsupported chart widget layout: {chart_type}")
            return

        # 2. Apply Custom AERA visual styling (Light Theme overrides)
        fig.update_layout(
            paper_bgcolor="rgba(0, 0, 0, 0)", # Transparent background wrapper
            plot_bgcolor="rgba(0, 0, 0, 0)",  # Transparent chart area background
            font=dict(
                family="'Inter', 'Segoe UI', sans-serif",
                size=11,
                color="#6B7280" # Secondary Text Gray
            ),
            margin=dict(l=40, r=20, t=20, b=40),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.3,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            hoverlabel=dict(
                bgcolor="#F8FAFC",
                font_color="#111827",
                font_size=11,
                font_family="'Inter', 'Segoe UI', sans-serif"
            )
        )

        # Apply axis overrides (Gridlines and Borders)
        if chart_type.lower() != "pie":
            fig.update_xaxes(
                showgrid=True,
                gridcolor="#F3F4F6", # Light grid borders
                linecolor="#E5E7EB",
                tickfont=dict(size=10),
                zeroline=False
            )
            fig.update_yaxes(
                showgrid=True,
                gridcolor="#F3F4F6", # Light grid borders
                linecolor="#E5E7EB",
                tickfont=dict(size=10),
                zeroline=False
            )

        # 3. Render inside container
        st.plotly_chart(fig, use_container_width=True)
