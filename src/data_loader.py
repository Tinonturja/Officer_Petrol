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

import re

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

    Supports two source layouts transparently:
      1. Already long-format (Officer_Name, Operation_Type, Date, Location, Distance).
      2. Original BANBATT-9 wide tracker — one row per officer/day with a
         4-column block (flag, "Dt & Day", "Loc", "Dstn") per operation type.
    """
    try:
        # header=None so we can sniff the layout ourselves.
        raw = pd.read_csv(url, header=None, dtype=str, keep_default_na=False)
    except Exception as exc:  # network, parse, auth, etc.
        st.error(f"Could not load live data from Google Sheets: {exc}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    if _looks_like_wide_tracker(raw):
        return _parse_wide_tracker(raw)
    return _preprocess(raw)


def is_air_operation(op_type: str) -> bool:
    """Return True if the operation type is an air patrol (LDAP / IDAP)."""
    return op_type in AIR_OPERATIONS


# ---------------------------------------------------------------------------
# Wide-format tracker parser
# ---------------------------------------------------------------------------

# Variants the operations cell uses in the sheet -> canonical name we expose.
_OP_ALIASES: dict[str, str] = {
    "TOB": "TOB",
    "ILDP": "ILDP",
    "MIL LDP": "Mil LDP",
    "ISDP": "ISDP",
    "MIL SDP": "Mil SDP",
    "LDAP": "LDAP",
    "IDAP": "IDAP",
    "FP TO UNISFA/MSD MOVCON CONVOY": "FP to UNISFA/MSD Movcon Convoy",
    "FP TO OTHER": "FP to Other",
    "CT PTL": "Ct Ptl",
}

_DAY_NAMES = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)


def _looks_like_wide_tracker(raw: pd.DataFrame) -> bool:
    """Heuristic: the wide tracker has 'Dt & Day' / 'Dstn' header tokens."""
    sample = raw.head(30).astype(str).apply(lambda c: c.str.strip())
    flat = sample.values.ravel()
    has_dt_day = any(v.lower() == "dt & day" for v in flat)
    has_dstn = any(v.lower() == "dstn" for v in flat)
    return has_dt_day and has_dstn


def _find_header_row(raw: pd.DataFrame) -> int | None:
    """Locate the row that contains the per-operation column headers."""
    for idx in range(min(40, len(raw))):
        row_vals = [str(v).strip().lower() for v in raw.iloc[idx].tolist()]
        if row_vals.count("dt & day") >= 2 and row_vals.count("dstn") >= 2:
            return idx
    return None


def _build_op_blocks(header_row: pd.Series) -> list[tuple[str, int, int, int]]:
    """
    From the header row, return [(canonical_op_type, date_col, loc_col, dist_col), ...].

    A block is recognised whenever a header cell matches one of our op-type
    aliases AND the next three columns are 'Dt & Day' / 'Loc' / 'Dstn'.
    """
    blocks: list[tuple[str, int, int, int]] = []
    cells = [str(v).strip() for v in header_row.tolist()]
    n = len(cells)
    for i in range(n - 3):
        canonical = _OP_ALIASES.get(cells[i].upper())
        if (
            canonical
            and cells[i + 1].lower() == "dt & day"
            and cells[i + 2].lower() == "loc"
            and cells[i + 3].lower() == "dstn"
        ):
            blocks.append((canonical, i + 1, i + 2, i + 3))
    return blocks


def _clean_date(value: str) -> pd.Timestamp:
    """Parse the free-form 'Dt & Day' cell into a Timestamp (NaT if unparseable)."""
    if not value:
        return pd.NaT
    text = _DAY_NAMES.sub("", str(value)).strip()
    text = re.sub(r"\s+", " ", text)
    return pd.to_datetime(text, errors="coerce", dayfirst=True)


def _to_float(value: str) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _parse_wide_tracker(raw: pd.DataFrame) -> pd.DataFrame:
    """Reshape the BANBATT-9 wide tracker into the canonical long-format frame."""
    header_idx = _find_header_row(raw)
    if header_idx is None:
        st.warning("Wide-format sheet detected but header row could not be located.")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    blocks = _build_op_blocks(raw.iloc[header_idx])
    if not blocks:
        st.warning("Wide-format sheet detected but no operation blocks could be mapped.")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    # Officer name lives in column 1, only on the *first* row of each officer's
    # group, so we forward-fill it over the data rows.
    data = raw.iloc[header_idx + 1 :].copy()
    name_col = 1
    data[name_col] = data[name_col].replace("", pd.NA).ffill()

    records: list[dict] = []
    for _, row in data.iterrows():
        officer = str(row.get(name_col, "")).strip()
        if not officer:
            continue
        for op_type, date_col, loc_col, dist_col in blocks:
            date_raw = str(row.get(date_col, "")).strip()
            loc_raw = str(row.get(loc_col, "")).strip()
            dist_raw = str(row.get(dist_col, "")).strip()
            # Skip the empty filler ("0" / "" / "-") used to keep the form aligned.
            if date_raw in {"", "0", "-", "#REF!"} and loc_raw in {"", "0", "-"}:
                continue
            date = _clean_date(date_raw)
            if pd.isna(date):
                continue
            records.append(
                {
                    "Officer_Name": officer,
                    "Operation_Type": op_type,
                    "Date": date,
                    "Location": loc_raw,
                    "Distance": _to_float(dist_raw),
                }
            )

    if not records:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    return pd.DataFrame.from_records(records, columns=REQUIRED_COLUMNS).reset_index(drop=True)


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
