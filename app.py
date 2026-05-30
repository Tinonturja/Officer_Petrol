import streamlit as st
from src.data_loader import load_data
from src.components import render_kpis, render_charts

# Configure the page
st.set_page_config(page_title="BANBATT Ops Dashboard", layout="wide", page_icon="🛡️")
st.title("🛡️ UNMISS BANBATT-9 Operations Dashboard")
st.markdown("Live operational tracking updated directly from central command logs.")

# Load the live data
df = load_data()

if not df.empty:
    # --- SIDEBAR FILTERS ---
    st.sidebar.header("Mission Filters")
    
    # Filter by Officer
    if 'Officer_Name' in df.columns:
        officers = st.sidebar.multiselect("Select Officer(s)", options=df['Officer_Name'].unique())
    else:
        officers = []
        
    # Filter by Operation Type (LDP, SDP, Air Patrols, etc.)
    if 'Operation_Type' in df.columns:
        ops = st.sidebar.multiselect("Select Operation Type(s)", options=df['Operation_Type'].unique())
    else:
        ops = []
        
    # Apply the filters to the dataframe
    filtered_df = df.copy()
    if officers:
        filtered_df = filtered_df[filtered_df['Officer_Name'].isin(officers)]
    if ops:
        filtered_df = filtered_df[filtered_df['Operation_Type'].isin(ops)]
        
    # --- RENDER DASHBOARD ---
    render_kpis(filtered_df)
    st.markdown("---")
    render_charts(filtered_df)
    
    # --- RAW DATA VIEW ---
    with st.expander("View Raw Operational Log"):
        st.dataframe(filtered_df, use_container_width=True)
else:
    st.info("Waiting for data stream from Google Sheets...")