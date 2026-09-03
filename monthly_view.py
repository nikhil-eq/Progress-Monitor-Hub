import pandas as pd
import streamlit as st

from pathlib import Path

from db import load_data

# --------------------------------------------------
#                  CONSTANTS
# --------------------------------------------------

workstreams_list_delivery = [
    'Initial Stratification - HIR',
    'Initial Stratification - NFMR',
    'Restratification - HIR',
    'Restratification - NFMR',
    'Restratification - Regen Check',
    'Change Detection',
    'Paddock Mapping and Digitisation',
    'Fire Impact Assessment',
    'Grid Creation',
    'Spatial Data Cleaning and Ingestion',
    'AD Survey Packages',
    'Field Survey Packages',
    'Adhoc Analysis',
    'Carbon Plus',
]


# --------------------------------------------------
#          DATA-SHAPING FUNCTION (unchanged)
# --------------------------------------------------

def get_monthly_project_status(month_df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per workstream for the selected month: all projects touched
    (with their latest status) listed together, plus a completed count.
    """
    project_status = (
        month_df.sort_values('date')
                .groupby(['workstream_name', 'project_name'], as_index=False)
                .last()[['workstream_name', 'project_name', 'current_status']]
    )

    project_status = project_status.sort_values(['workstream_name', 'project_name'])

    project_status['project_display'] = (
        project_status['project_name'] + ' (' + project_status['current_status'] + ')'
    )

    is_completed = project_status['current_status'].str.lower() == 'completed'
    project_status['is_completed'] = is_completed

    result = (
        project_status.groupby('workstream_name')
                       .agg(
                           project_names=('project_display', lambda s: ' • '.join(s)),
                           completed_count=('is_completed', 'sum'),
                           total_projects=('project_name', 'count'),
                       )
                       .reset_index()
    )

    result['workstream_name'] = pd.Categorical(
        result['workstream_name'], categories=workstreams_list_delivery, ordered=True
    )
    result = result.sort_values('workstream_name').reset_index(drop=True)
    return result


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

def page3():
    inject_css()
    st.title('Monthly View')

    with st.container(border=True):
        st.markdown('## Monthly Work Log')

        df = load_data()
        df = df[df['workstream_name'].isin(workstreams_list_delivery)].copy()

        months = sorted(df['month_start'].dropna().unique(), reverse=True)
        month_labels = {m: f"{pd.Timestamp(m).strftime('%B %Y')}" for m in months}
        label_to_month = {v: k for k, v in month_labels.items()}
        month_label_options = list(month_labels.values())

        if not month_label_options:
            st.markdown('_No dated entries found._')
            return

        if ('selected_month_label' not in st.session_state
                or st.session_state.selected_month_label not in month_label_options):
            st.session_state.selected_month_label = month_label_options[0]

        st.selectbox('Select Month', options=month_label_options, key='selected_month_label')

    current_month = label_to_month[st.session_state.selected_month_label]
    month_df = df[df['month_start'] == current_month]

    result = get_monthly_project_status(month_df)
    result = result.rename(columns={
        'workstream_name': 'Workstream',
        'project_names': 'Project Name',
        'completed_count': 'Completed Projects Count',
        'total_projects': 'Total Projects Touched',
    })

    with st.container(border=True):
        st.dataframe(result, use_container_width=True, height=min(900, 60 + 35 * len(result)))

    with st.container(border=True):
        completed_sum = result['Completed Projects Count'].sum() if not result.empty else 0
        touched_sum = result['Total Projects Touched'].sum() if not result.empty else 0
        st.markdown(f"**{completed_sum}** projects completed in {st.session_state.selected_month_label}")
        st.markdown(f"**{touched_sum}** projects touched in {st.session_state.selected_month_label}")


page3()