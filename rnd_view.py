import pandas as pd
import streamlit as st

from pathlib import Path

from db import load_data

# --------------------------------------------------
#                  CONSTANTS
# --------------------------------------------------

TARGET_WORKSTREAM = 'research and development'


# --------------------------------------------------
#          DATA-SHAPING FUNCTION (unchanged)
# --------------------------------------------------

def load_rd_log() -> pd.DataFrame:
    df = load_data()

    mask = df['workstream_name'].str.lower() == TARGET_WORKSTREAM
    rd_df = df[mask].copy()

    rd_df = rd_df.sort_values('date', ascending=False)
    return rd_df[['user_name', 'stage', 'rnd_explaination', 'time_spent']]


# --------------------------------------------------
#                   STYLING HELPER
# --------------------------------------------------

def inject_css():
    st.markdown("""
        <style>
        .nav-card:hover {
            background: #162233 !important;
            border-color: #2a3f55 !important;
            transform: translateY(-2px);
        }
        .nav-card:active {
            transform: translateY(0);
        }
        </style>
    """, unsafe_allow_html=True)


# --------------------------------------------------
#                       PAGE
# --------------------------------------------------

def page6():
    inject_css()
    st.title('Research and Development')

    st.markdown('# Research and Development')
    st.markdown('All logged R&D work, most recent first.')

    rd_df = load_rd_log()

    if rd_df.empty:
        st.markdown('_No Research and Development entries found._')
        return

    result = rd_df.rename(columns={
        'user_name': 'Team Member',
        'stage': 'Stage',
        'rnd_explaination': 'Description',
        'time_spent': 'Time Spent (hrs)',
    })

    st.markdown(f"**{len(result)}** entries logged")
    st.dataframe(result, use_container_width=True, height=min(900, 60 + 35 * len(result)))


page6()