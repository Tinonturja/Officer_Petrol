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

from src.data_loader import OPERATION_TYPES

# ---------------------------------------------------------------------------
# Visual identity
# ---------------------------------------------------------------------------

# Clean, corporate-friendly Plotly template used by every figure on the page.
PLOTLY_TEMPLATE: str = "plotly_white"

# Standard layout margins — uncluttered, high-end feel.
LAYOUT_MARGIN: dict[str, int] = dict(l=20, r=20, t=40, b=20)

# A muted, military-corporate palette: deep greens, khaki, steel-blue, amber.
_CATEGORY_COLOURS = [
    "#1B4332",  # forest
    "#3E5641",  # olive
    "#519872",  # mid green
    "#A4B494",  # khaki
    "#9C6644",  # earth
    "#D9AE61",  # sand
    "#4C78A8",  # steel
    "#2A4D69",  # navy
    "#7D8491",  # slate
    "#B7B07F",  # stone
]

# Stable colour assignment so the same Operation_Type is always the same hue
# across the stacked bar, the donut, and the timeline.
OPERATION_COLOURS: dict[str, str] = {
    op: _CATEGORY_COLOURS[i % len(_CATEGORY_COLOURS)]
    for i, op in enumerate(OPERATION_TYPES)
}


def _apply_house_style(fig) -> None:
    """Apply the shared layout settings to a Plotly figure in-place."""
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        margin=LAYOUT_MARGIN,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.0,
            title_text="",
        ),
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#1B4332",
            font_size=12,
        ),
    )


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
          .assign(Day=lambda d: d["Date"].dt.normalize())
          .groupby("Day", as_index=False)
          .size()
          .rename(columns={"size": "Operations"})
          .sort_values("Day")
    )

    fig = px.line(
        tempo,
        x="Day",
        y="Operations",
        markers=True,
        labels={"Operations": "Operations / Day", "Day": "Date"},
        color_discrete_sequence=["#1B4332"],
        hover_data={"Day": "|%d %b %Y", "Operations": ":,d"},
    )
    fig.update_traces(line=dict(width=2.5), marker=dict(size=8))
    _apply_house_style(fig)
    fig.update_layout(hovermode="x unified", xaxis=dict(showgrid=False))
    st.plotly_chart(fig, use_container_width=True)


def render_distance_by_officer(df: pd.DataFrame) -> None:
    """
    Stacked horizontal bar chart — total kilometres per officer, broken down
    by Operation_Type so each segment is visible and colour-coded.
    """
    st.subheader("Distance Covered by Officer (KM)")

    required = {"Officer_Name", "Operation_Type", "Distance"}
    if df.empty or not required.issubset(df.columns):
        st.info("Officer / distance data unavailable.")
        return

    # Aggregate while *preserving* the operation-type breakdown so each
    # officer's bar is composed of one segment per op-type they performed.
    by_officer_op = (
        df.groupby(["Officer_Name", "Operation_Type"], as_index=False)["Distance"]
          .sum()
    )

    # Sort officers by their total distance so the longest bars are at the top.
    officer_order = (
        by_officer_op.groupby("Officer_Name")["Distance"]
                     .sum()
                     .sort_values(ascending=True)
                     .index.tolist()
    )

    fig = px.bar(
        by_officer_op,
        x="Distance",
        y="Officer_Name",
        color="Operation_Type",
        orientation="h",
        labels={
            "Distance": "Distance (KM)",
            "Officer_Name": "Officer",
            "Operation_Type": "Operation",
        },
        color_discrete_map=OPERATION_COLOURS,
        category_orders={
            "Officer_Name": officer_order,
            "Operation_Type": list(OPERATION_TYPES),
        },
        hover_data={
            "Officer_Name": True,
            "Operation_Type": True,
            "Distance": ":,.0f",
        },
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Operation: %{customdata[0]}<br>"
            "Distance: %{x:,.0f} KM<extra></extra>"
        ),
        customdata=by_officer_op[["Operation_Type"]].values,
    )
    _apply_house_style(fig)
    fig.update_layout(
        barmode="stack",
        yaxis=dict(title=None),
        xaxis=dict(title="Distance (KM)"),
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
        color="Operation_Type",
        color_discrete_map=OPERATION_COLOURS,
        category_orders={"Operation_Type": list(OPERATION_TYPES)},
    )
    fig.update_traces(
        textinfo="percent+label",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Operations: %{value}<br>"
            "Share: %{percent}<extra></extra>"
        ),
    )
    _apply_house_style(fig)
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def render_operations_timeline(df: pd.DataFrame) -> None:
    """
    Gantt-style timeline of every operation.

    X-axis : Date
    Y-axis : Officer
    Colour : Operation_Type
    Size   : Distance (KM)

    A single dot = a single operation, so two City Patrols on different days
    are visibly distinct on the same officer's row.
    """
    st.subheader("Operations Timeline")

    required = {"Officer_Name", "Operation_Type", "Date", "Location", "Distance"}
    if df.empty or not required.issubset(df.columns):
        st.info("Timeline requires officer, operation, date, location and distance fields.")
        return

    timeline_df = df.dropna(subset=["Date"]).copy()
    if timeline_df.empty:
        st.info("No dated operations to plot.")
        return

    # Officers sorted by their first activity date so the chart reads
    # chronologically from top to bottom.
    officer_order = (
        timeline_df.groupby("Officer_Name")["Date"]
                   .min()
                   .sort_values(ascending=False)
                   .index.tolist()
    )

    fig = px.scatter(
        timeline_df,
        x="Date",
        y="Officer_Name",
        color="Operation_Type",
        size="Distance",
        size_max=22,
        labels={
            "Date": "Operation Date",
            "Officer_Name": "Officer",
            "Operation_Type": "Operation",
            "Distance": "Distance (KM)",
            "Location": "Location",
        },
        color_discrete_map=OPERATION_COLOURS,
        category_orders={
            "Officer_Name": officer_order,
            "Operation_Type": list(OPERATION_TYPES),
        },
        hover_data={
            "Officer_Name": True,
            "Operation_Type": True,
            "Date": "|%d %b %Y",
            "Location": True,
            "Distance": ":,.0f",
        },
    )
    fig.update_traces(
        marker=dict(line=dict(width=1, color="white"), opacity=0.9),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Operation: %{customdata[1]}<br>"
            "Date: %{x|%d %b %Y}<br>"
            "Location: %{customdata[2]}<br>"
            "Distance: %{customdata[3]:,.0f} KM<extra></extra>"
        ),
        customdata=timeline_df[
            ["Officer_Name", "Operation_Type", "Location", "Distance"]
        ].values,
    )
    _apply_house_style(fig)
    fig.update_layout(
        xaxis=dict(title="Date", showgrid=True, gridcolor="#EEEEEE"),
        yaxis=dict(title=None, autorange="reversed"),
        height=max(380, 28 * len(officer_order) + 120),
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Composite layout
# ---------------------------------------------------------------------------

def render_charts(df: pd.DataFrame) -> None:
    """Compose every chart into the main dashboard grid."""
    if df.empty:
        st.warning("No data matches the current filters.")
        return

    # Row 1 — daily tempo (full width).
    render_time_series(df)

    st.markdown("&nbsp;")

    # Row 2 — chronological per-officer timeline (full width).
    render_operations_timeline(df)

    st.markdown("&nbsp;")

    # Row 3 — stacked distance bar (left) + operation donut (right).
    left, right = st.columns((1.3, 1))
    with left:
        render_distance_by_officer(df)
    with right:
        render_operation_donut(df)
