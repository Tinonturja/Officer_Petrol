"""
Presentation layer for the BANBATT-9 Operations Dashboard.

All Plotly figures and Streamlit widgets live here so that `app.py` stays a
thin orchestration layer.  Each function takes a *filtered* DataFrame and is
responsible for one well-defined panel of the dashboard.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

# A military-friendly palette: muted greens / khakis / steel blue.
_PALETTE = [
    "#3E5641", "#A4B494", "#519872", "#1B4332",
    "#9C6644", "#4C78A8", "#D9AE61", "#7D8491",
    "#2A4D69", "#B7B07F",
]


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

def render_kpis(df: pd.DataFrame) -> None:
    """Render the three top-level KPI cards."""
    total_ops = len(df)
    total_km = float(df["Distance"].sum()) if "Distance" in df.columns else 0.0

    if "Location" in df.columns and not df.empty:
        modes = df["Location"].mode()
        most_frequent_location = modes.iloc[0] if not modes.empty else "N/A"
    else:
        most_frequent_location = "N/A"

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Operations", f"{total_ops:,}")
    col2.metric("Total Distance (KM)", f"{total_km:,.0f}")
    col3.metric("Most Frequent Location", most_frequent_location)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def render_time_series(df: pd.DataFrame) -> None:
    """Daily operational tempo — number of operations over time."""
    st.subheader("Operational Tempo Over Time")

    if df.empty or "Date" not in df.columns:
        st.info("No dated operations to plot.")
        return

    tempo = (
        df.dropna(subset=["Date"])
          .groupby(df["Date"].dt.date)
          .size()
          .reset_index(name="Operations")
          .rename(columns={"Date": "Day"})
    )
    tempo["Day"] = pd.to_datetime(tempo["Day"])
    tempo = tempo.sort_values("Day")

    fig = px.line(
        tempo,
        x="Day",
        y="Operations",
        markers=True,
        labels={"Operations": "Operations / Day", "Day": "Date"},
        color_discrete_sequence=[_PALETTE[0]],
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        hovermode="x unified",
        xaxis=dict(showgrid=False),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_distance_by_officer(df: pd.DataFrame) -> None:
    """Horizontal bar chart — total kilometres covered per officer."""
    st.subheader("Total Distance by Officer (KM)")

    if df.empty or not {"Officer_Name", "Distance"}.issubset(df.columns):
        st.info("Officer / distance data unavailable.")
        return

    by_officer = (
        df.groupby("Officer_Name", as_index=False)["Distance"]
          .sum()
          .sort_values("Distance", ascending=True)
    )

    fig = px.bar(
        by_officer,
        x="Distance",
        y="Officer_Name",
        orientation="h",
        text="Distance",
        labels={"Distance": "Total KM", "Officer_Name": "Officer"},
        color="Distance",
        color_continuous_scale=["#A4B494", "#1B4332"],
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        coloraxis_showscale=False,
        yaxis=dict(title=None),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_operation_donut(df: pd.DataFrame) -> None:
    """Donut chart — share of operations by Operation_Type."""
    st.subheader("Operation Mix")

    if df.empty or "Operation_Type" not in df.columns:
        st.info("No operation-type data to display.")
        return

    breakdown = (
        df["Operation_Type"]
          .value_counts()
          .rename_axis("Operation_Type")
          .reset_index(name="Count")
    )

    fig = px.pie(
        breakdown,
        names="Operation_Type",
        values="Count",
        hole=0.55,
        color_discrete_sequence=_PALETTE,
    )
    fig.update_traces(
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Operations: %{value}<br>Share: %{percent}",
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Composite layout
# ---------------------------------------------------------------------------

def render_charts(df: pd.DataFrame) -> None:
    """Compose the three charts into the main dashboard grid."""
    if df.empty:
        st.warning("No data matches the current filters.")
        return

    # Row 1: full-width tempo line chart.
    render_time_series(df)

    st.markdown("&nbsp;")

    # Row 2: distance bar (left) + operation donut (right).
    left, right = st.columns((1.2, 1))
    with left:
        render_distance_by_officer(df)
    with right:
        render_operation_donut(df)
