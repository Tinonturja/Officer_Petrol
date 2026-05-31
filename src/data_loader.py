"""
Live data loader for the BANBATT-9 Operations Dashboard.

The source-of-truth is a Google Sheet published to the web as CSV.  Editing the
sheet propagates to the dashboard within `ttl` seconds, so the operations cell
never has to redeploy the app to refresh figures.

Expected long-format columns (after normalisation):
    Officer_Name : str
    Operation_Type : str   # one of the 10 canonical operations below
    Date         : datetime64[ns]
    Location     : str
    Distance     : float   # kilometres
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Published-to-web CSV link of the master tracker
# ("Offrs Ptl Summary (1)_2.xlsx" -> File -> Share -> Publish to web -> CSV).
SHEET_URL: str = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRvxRuRfcUmozJnOCZicRe5gLJ3QPqvPh1NZMGYZWH4Nt88UUSNYn-hCvmC4pJDKg"
    "/pub?output=csv"
)

# Canonical list of the 10 operation types tracked by BANBATT-9.
OPERATION_TYPES: tuple[str, ...] = (
    "TOB",                              # Temporary Operating Base
    "ILDP",                             # Integrated Long Distance Patrol
    "Mil LDP",                          # Military Long Distance Patrol
    "ISDP",                             # Integrated Short Distance Patrol
    "Mil SDP",                          # Military Short Distance Patrol
    "LDAP",                             # Long Dynamic Air Patrol
    "IDAP",                             # Integrated Dynamic Air Patrol
    "FP to UNISFA/MSD Movcon Convoy",   # Force Protection (Escort)
    "FP to Other",                      # Force Protection (Other)
    "Ct Ptl",                           # City Patrol
)

# Air-patrol operations are flagged separately because their distance scale
# differs from ground convoys.
AIR_OPERATIONS: frozenset[str] = frozenset({"LDAP", "IDAP"})

REQUIRED_COLUMNS: tuple[str, ...] = (
    "Officer_Name",
    "Operation_Type",
    "Date",
    "Location",
    "Distance",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner="Fetching live ops log…")
def load_data(url: str = SHEET_URL) -> pd.DataFrame:
    """
    Pull the published Google Sheet as CSV and return a clean long-format frame.

    The result is cached for 60 seconds so concurrent users share a single
    network round-trip.  Any edit to the sheet shows up on the dashboard
    within one TTL window.
    """
    try:
        raw = pd.read_csv(url)
    except Exception as exc:  # network, parse, auth, etc.
        st.error(f"Could not load live data from Google Sheets: {exc}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    return _preprocess(raw)


def is_air_operation(op_type: str) -> bool:
    """Return True if the operation type is an air patrol (LDAP / IDAP)."""
    return op_type in AIR_OPERATIONS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names, types and obviously bad rows."""
    if df.empty:
        return df

    # 1. Tidy column headers
    df = df.copy()
    df.columns = df.columns.str.strip()

    # 2. Allow legacy "Distance_KM" header from earlier versions of the sheet
    if "Distance" not in df.columns and "Distance_KM" in df.columns:
        df = df.rename(columns={"Distance_KM": "Distance"})

    # 3. Strip text columns
    for col in ("Officer_Name", "Operation_Type", "Location"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # 4. Coerce numeric / datetime columns
    if "Distance" in df.columns:
        df["Distance"] = pd.to_numeric(df["Distance"], errors="coerce").fillna(0.0)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)

    # 5. Drop rows that are missing critical fields
    must_have = [c for c in ("Officer_Name", "Operation_Type", "Date") if c in df.columns]
    if must_have:
        df = df.dropna(subset=must_have)

    # 6. Keep a stable column order, but tolerate extra columns from the sheet
    ordered = [c for c in REQUIRED_COLUMNS if c in df.columns]
    extras = [c for c in df.columns if c not in ordered]
    return df[ordered + extras].reset_index(drop=True)
