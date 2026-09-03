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

def load_workstream_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Loads and cleans the raw log, then returns three things:
      1. summary          -> one row per workstream, with a 'completed' count
      2. project_status    -> one row per (workstream, project), with its is_complete flag
      3. monthly_completions -> one row per (workstream, project) that IS complete, with the
                                month it was completed in (based on its most recent
                                'completed' + non-Peer-Review dated entry)
    """
    df = load_data()

    df = df.dropna(subset=['workstream_name', 'project_name'])

    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['current_status'] = df['current_status'].astype(str).str.strip().str.lower()
    df['stage'] = df['stage'].astype(str).str.strip()
    df['workstream_name'] = df['workstream_name'].astype(str).str.strip()

    # 1. restrict to only the workstreams we care about
    df = df[df['workstream_name'].isin(workstreams_list_delivery)]

    # 2. rows sitting in Peer Review don't count toward "completed",
    #    even if current_status happens to say Completed
    eligible = df[df['stage'].str.lower() != 'peer review']

    project_flags = (
        eligible.groupby(['workstream_name', 'project_name'])['current_status']
                .apply(lambda s: s.eq('completed').any())
                .reset_index(name='is_complete')
    )

    # total_projects should reflect ALL known projects per workstream
    # (including ones currently stuck in Peer Review), so use the
    # unfiltered df for the denominator
    all_projects = (
        df.groupby(['workstream_name', 'project_name'])
          .size()
          .reset_index(name='_')[['workstream_name', 'project_name']]
    )

    project_status = all_projects.merge(
        project_flags, on=['workstream_name', 'project_name'], how='left'
    )
    project_status['is_complete'] = project_status['is_complete'].fillna(False)

    summary = (
        project_status.groupby('workstream_name')
                       .agg(completed=('is_complete', 'sum'))
                       .reset_index()
    )

    summary['workstream_name'] = pd.Categorical(
        summary['workstream_name'], categories=workstreams_list_delivery, ordered=True
    )
    summary = summary.sort_values('workstream_name').reset_index(drop=True)

    # ------------------------------------------------------------------
    # 3. figure out WHICH MONTH each completed project was completed in
    # ------------------------------------------------------------------
    completed_rows = eligible[eligible['current_status'] == 'completed']

    # most recent completed-and-eligible dated entry per project
    last_completion = (
        completed_rows.sort_values('date')
                       .groupby(['workstream_name', 'project_name'], as_index=False)
                       .last()[['workstream_name', 'project_name', 'date']]
    )
    last_completion['month'] = last_completion['date'].dt.to_period('M').dt.to_timestamp()

    monthly_completions = last_completion[['workstream_name', 'project_name', 'month']]

    return summary, project_status, monthly_completions


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

def page4():
    inject_css()
    st.title('Lifetime View')

    with st.container(border=True):
        st.markdown('## Lifetime View')

    with st.container(border=True):
        st.markdown('Number of **Projects Completed (Lifetime)** in Each of the Workstreams')

        summary_df, project_status_df, monthly_completions_df = load_workstream_data()

        st.dataframe(summary_df, use_container_width=True,
                     height=min(900, 60 + 35 * len(summary_df)))

    # ------------------------------------------------------------------
    #  Panels: completed projects by month, broken out per workstream
    # ------------------------------------------------------------------
    st.markdown("&nbsp;")  # spacer between the summary table and the panels below
    st.markdown("## Completed Projects by Workstream")

    for workstream in workstreams_list_delivery:

        ws_completions = monthly_completions_df[
            monthly_completions_df['workstream_name'] == workstream
        ]

        with st.expander(workstream):
            if ws_completions.empty:
                st.markdown("_No completed projects yet._")
                continue

            monthly_table = (
                ws_completions.groupby('month')['project_name']
                              .apply(lambda s: ', '.join(sorted(s)))
                              .reset_index()
                              .rename(columns={'project_name': 'Projects Completed'})
            )
            monthly_table['Month'] = monthly_table['month'].dt.strftime('%B %Y')
            monthly_table = monthly_table.sort_values('month', ascending=False)
            monthly_table = monthly_table[['Month', 'Projects Completed']]

            st.dataframe(monthly_table, use_container_width=True,
                         height=min(500, 60 + 35 * len(monthly_table)))


page4()