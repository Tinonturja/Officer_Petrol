import pandas as pd
import streamlit as st

# Your live Google Sheets CSV link
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRvxRuRfcUmozJnOCZicRe5gLJ3QPqvPh1NZMGYZWH4Nt88UUSNYn-hCvmC4pJDKg/pub?output=csv"

@st.cache_data(ttl=60) 
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        
        # Clean up column names just in case there are trailing spaces
        df.columns = df.columns.str.strip()
        
        # Ensure distance is treated as a number for calculations
        if 'Distance_KM' in df.columns:
            df['Distance_KM'] = pd.to_numeric(df['Distance_KM'], errors='coerce').fillna(0)
            
        return df
    except Exception as e:
        st.error(f"Error loading live data from Google Sheets: {e}")
        return pd.DataFrame()