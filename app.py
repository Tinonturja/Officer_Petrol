"""
BANBATT-9 Operations Dashboard – Streamlit entry point.

Run locally:
    streamlit run app.py

Deploy:
    Push to GitHub and connect the repo to Streamlit Community Cloud.
    The data refreshes automatically every 60 seconds from the published
    Google-Sheet CSV (see src/data_loader.py).
"""

from __future__ import annotations

import streamlit as st

from src.data_loader import OPERATION_TYPES, load_data
from src.components import render_charts, render_kpis

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="BANBATT-9 Ops Dashboard",
    layout="wide",
    page_icon="🛡️",
)

st.title("🛡️ UNMISS BANBATT-9 Operations Dashboard")
st.caption(
    "Live operational tracking — data syncs from the central command "
    "Google-Sheet log every 60 seconds."
)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

df = load_data()

if df.empty:
    st.info("Waiting for data stream from Google Sheets…")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar — filters
# ---------------------------------------------------------------------------

st.sidebar.header("Mission Filters")

officer_options = sorted(df["Officer_Name"].dropna().unique().tolist())
selected_officers = st.sidebar.multiselect(
    "Officer(s)",
    options=officer_options,
    default=[],
    placeholder="All officers",
)

# Show only operation types that actually appear in the data, but ordered
# according to the canonical doctrine list.
present_ops = set(df["Operation_Type"].dropna().unique())
op_options = [op for op in OPERATION_TYPES if op in present_ops] + sorted(
    present_ops - set(OPERATION_TYPES)
)
selected_ops = st.sidebar.multiselect(
    "Operation Type(s)",
    options=op_options,
    default=[],
    placeholder="All operation types",
)

# Optional date range — only shown when valid dates exist.
if "Date" in df.columns and df["Date"].notna().any():
    min_date = df["Date"].min().date()
    max_date = df["Date"].max().date()
    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
else:
    date_range = None

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh data now", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

filtered = df.copy()

if selected_officers:
    filtered = filtered[filtered["Officer_Name"].isin(selected_officers)]

if selected_ops:
    filtered = filtered[filtered["Operation_Type"].isin(selected_ops)]

if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    mask = (filtered["Date"].dt.date >= start) & (filtered["Date"].dt.date <= end)
    filtered = filtered[mask]

# ---------------------------------------------------------------------------
# Render dashboard
# ---------------------------------------------------------------------------

render_kpis(filtered)
st.markdown("---")
render_charts(filtered)

with st.expander("📋 Raw operational log"):
    st.dataframe(filtered, use_container_width=True, hide_index=True)
