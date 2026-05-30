import plotly.express as px
import streamlit as st

def render_kpis(df):
    total_ops = len(df)
    
    # Safely calculate total KM
    total_km = df['Distance_KM'].sum() if 'Distance_KM' in df.columns else 0
    
    # Safely find the busiest location
    if 'Location' in df.columns and not df.empty:
        busiest_loc = df['Location'].mode()[0] 
    else:
        busiest_loc = "N/A"
    
    # Display the metrics across 3 columns
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Operations Count", f"{total_ops}")
    col2.metric("Total Distance Covered", f"{total_km:,.0f} KM")
    col3.metric("Busiest Location", busiest_loc)

def render_charts(df):
    if df.empty:
        st.warning("No data available to display charts. Check your filters.")
        return

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Distance Covered by Officer")
        if 'Officer_Name' in df.columns and 'Distance_KM' in df.columns:
            dist_df = df.groupby('Officer_Name')['Distance_KM'].sum().reset_index()
            # Sort for better visual hierarchy
            dist_df = dist_df.sort_values(by='Distance_KM', ascending=True)
            
            fig1 = px.bar(
                dist_df, x='Distance_KM', y='Officer_Name', orientation='h',
                labels={'Distance_KM': 'Total KM', 'Officer_Name': 'Officer'},
                color_discrete_sequence=['#4C78A8']
            )
            st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.subheader("Operations Breakdown")
        if 'Operation_Type' in df.columns:
            op_df = df['Operation_Type'].value_counts().reset_index()
            op_df.columns = ['Operation_Type', 'Count']
            
            fig2 = px.pie(
                op_df, values='Count', names='Operation_Type', hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            # Hover data to show the specific UNMISS operations clearly
            fig2.update_traces(textinfo='percent+label', hoverinfo='label+value')
            st.plotly_chart(fig2, use_container_width=True)