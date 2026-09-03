import pandas as pd
import streamlit as st

from pathlib import Path

import matplotlib.pyplot as plt

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
    'Fire Impact Assessment',
    'Grid Creation',
    'Spatial Data Cleaning and Ingestion',
    'AD Survey Packages',
    'Field Survey Packages',
    'Adhoc Analysis',
    'Carbon Plus',
]

rnd_list = [
    'Research and Development',
    'Miscellaneous',
    'Paddock Mapping and Digitisation'
]


# --------------------------------------------------
#          DATA-SHAPING FUNCTIONS (unchanged)
# --------------------------------------------------

def get_latest_status_map(df: pd.DataFrame) -> pd.DataFrame:
    """Each (user, workstream, project)'s latest known status/stage,
    based on that user's most recent dated entry for that project."""
    return (
        df.sort_values('date')
          .groupby(['user_name', 'workstream_name', 'project_name'], as_index=False)
          .last()[['user_name', 'workstream_name', 'project_name', 'current_status', 'stage']]
          .rename(columns={'current_status': 'latest_status', 'stage': 'latest_stage'})
    )


def get_workstream_ops_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per workstream: how many distinct projects have been touched,
    how many are completed, and a bullet-point breakdown of project names
    (every project touched, plus a separate list of the ones still In Progress).
    """
    scoped = df[df['workstream_name'].isin(workstreams_list_delivery)].copy()
    scoped['current_status'] = scoped['current_status'].str.strip().str.lower()

    project_status = (
        scoped.sort_values('date')
              .groupby(['workstream_name', 'project_name'], as_index=False)
              .last()[['workstream_name', 'project_name', 'current_status']]
    )

    def build_row(group: pd.DataFrame) -> pd.Series:
        completed = group[group['current_status'] == 'completed']
        in_progress = group[group['current_status'] != 'completed']

        all_names = "\n".join(f"• {n}" for n in sorted(group['project_name']))
        in_progress_names = (
            "\n".join(f"• {n}" for n in sorted(in_progress['project_name']))
            if not in_progress.empty else "—"
        )

        return pd.Series({
            'total_touched': group['project_name'].nunique(),
            'completed_count': len(completed),
            'all_projects': all_names,
            'in_progress_projects': in_progress_names,
        })

    summary = (
        project_status.groupby('workstream_name')
                       .apply(build_row, include_groups=False)
                       .reset_index()
    )

    summary['workstream_name'] = pd.Categorical(
        summary['workstream_name'], categories=workstreams_list_delivery, ordered=True
    )
    summary = summary.sort_values('workstream_name').reset_index(drop=True)
    return summary


def get_paddock_summary(df: pd.DataFrame) -> pd.DataFrame:
    scoped = df[df['workstream_name'].isin(['Paddock Mapping and Digitisation'])].copy()
    scoped['current_status'] = scoped['current_status'].str.strip().str.lower()

    project_status = (
        scoped.sort_values('date')
              .groupby(['workstream_name', 'project_name'], as_index=False)
              .last()[['workstream_name', 'project_name', 'current_status']]
    )

    def build_row(group: pd.DataFrame) -> pd.Series:
        completed = group[group['current_status'] == 'completed']
        in_progress = group[group['current_status'] != 'completed']

        all_names = "\n".join(f"• {n}" for n in sorted(group['project_name']))
        in_progress_names = (
            "\n".join(f"• {n}" for n in sorted(in_progress['project_name']))
            if not in_progress.empty else "—"
        )

        return pd.Series({
            'total_touched': group['project_name'].nunique(),
            'completed_count': len(completed),
            'all_projects': all_names,
            'in_progress_projects': in_progress_names,
        })

    summary = (
        project_status.groupby('workstream_name')
                       .apply(build_row, include_groups=False)
                       .reset_index()
    )

    summary['workstream_name'] = pd.Categorical(
        summary['workstream_name'], categories=['Paddock Mapping and Digitisation'], ordered=True
    )
    summary = summary.sort_values('workstream_name').reset_index(drop=True)

    summary = summary.rename(columns={
        'workstream_name': 'Workstream',
        'total_touched': 'Projects Planned',
        'completed_count': 'Projects Completed',
        'all_projects': 'All Projects',
        'in_progress_projects': 'In Progress Projects'
    })

    return summary


def get_workstream_rnd_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per remaining R&D stage (excludes Paddock Mapping and Digitisation —
    see get_paddock_summary for that). Detail column lists that stage's logged
    rnd_explaination entries.
    """
    scoped = df[df['workstream_name'].isin(rnd_list)].copy()
    scoped = df[~df['stage']].isin({'Meetings', 'Debugging'})
    scoped['stage'] = scoped['stage'].str.strip()
    scoped['rnd_explaination'] = scoped['rnd_explaination'].astype(str).str.strip()

    paddock_stage_names = {'Processing', 'Completed'}
    scoped = scoped[~scoped['stage'].isin(paddock_stage_names)]

    stage_display_names = {
        'iMAD': 'iMAD: Change Detection',
        'WS3: ALS-to-CPC': 'WS3: ALS-to-CPC',
        'Fire Impact Assessment': 'Fire Impact Assessment',
        'WS2: Allometric Equations': 'WS2: Allometric Equations',
    }
    scoped['stage'] = scoped['stage'].replace(stage_display_names)

    def build_row(group: pd.DataFrame) -> pd.Series:
        explanations = group['rnd_explaination'].dropna()
        explanations = explanations[explanations != '']
        detail = "\n".join(f"• {e}" for e in explanations) if not explanations.empty else "—"

        return pd.Series({
            'planned': group['project_name'].nunique(),
            'detail': detail,
        })

    summary = (
        scoped.groupby('stage', group_keys=True)
              .apply(build_row, include_groups=False)
              .reset_index()
    )

    summary = summary.sort_values('stage').reset_index(drop=True)
    summary = summary.drop(columns=['planned'])
    summary = summary.rename(columns={
        'stage': 'Workstream',
        'detail': 'Progress',
    })
    return summary


def get_user_workstream_hours(week_df: pd.DataFrame) -> pd.DataFrame:
    """
    Hours per (user, workstream) for the given week, across ALL workstreams
    (no filtering to workstreams_list_delivery — Miscellaneous, R&D, etc. included).
    """
    hours = (
        week_df.groupby(['user_name', 'workstream_name'], as_index=False)
               .agg(hours=('time_spent', 'sum'))
    )
    pivot = hours.pivot(index='user_name', columns='workstream_name', values='hours').fillna(0)
    return pivot


# --------------------------------------------------
#                   STYLING HELPERS
# --------------------------------------------------

def inject_css():
    st.markdown("""
        <style>
        /* dark theme table styling for the HTML bullet tables below */
        table.bullet-table {
            width: 100%;
            border-collapse: collapse;
            background: transparent;
            color: #e8eef4;
        }
        table.bullet-table th, table.bullet-table td {
            border-bottom: 1px solid #1a2a3a;
            border-right: 1px solid #1a2a3a;
            padding: 8px 16px;
            text-align: left;
            vertical-align: top;
            white-space: pre-line;
        }
        table.bullet-table th:last-child, table.bullet-table td:last-child {
            border-right: none;
        }
        table.bullet-table tr:hover {
            background: #162233;
        }
        </style>
    """, unsafe_allow_html=True)


def render_bullet_table(df: pd.DataFrame):
    """Render a dataframe as HTML so that '\\n'-separated bullet lists inside
    cells show as real line breaks (st.dataframe collapses newlines)."""
    display_df = df.copy()
    for col in display_df.columns:
        if display_df[col].dtype == object:
            display_df[col] = display_df[col].astype(str).str.replace("\n", "<br>")

    html = display_df.to_html(escape=False, index=False, classes="bullet-table", border=0)
    st.markdown(html, unsafe_allow_html=True)


# --------------------------------------------------
#                       PAGE
# --------------------------------------------------


st.markdown("""
    <style>
    div.st-key-weekly_view_card {
        background-color: #000000 !important;
        border-radius: 8px;
        padding: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    div.st-key-weekly_view_card2 {
        background-color: #000000 !important;
        border-radius: 8px;
        padding: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    div.st-key-weekly_view_card3 {
        background-color: #000000 !important;
        border-radius: 8px;
        padding: 1rem;
    }
    </style>
""", unsafe_allow_html=True)


def page2():
    st.markdown('### Weekly View')
    inject_css()

    with st.container(border=True, key = "weekly_view_card"):
        st.markdown('#### Weekly Work Log')

        df = load_data()

        weeks = sorted(df['week_start'].dropna().unique(), reverse=True)
        week_labels = {w: f"Week of {pd.Timestamp(w).strftime('%d %b %Y')}" for w in weeks}
        label_to_week = {v: k for k, v in week_labels.items()}
        week_label_options = list(week_labels.values())

        if not week_label_options:
            st.markdown('_No dated entries found._')
            return

        if ('selected_week_label' not in st.session_state
                or st.session_state.selected_week_label not in week_label_options):
            st.session_state.selected_week_label = week_label_options[0]

        st.selectbox('Select Week', options=week_label_options, key='selected_week_label')

    current_week = label_to_week[st.session_state.selected_week_label]
    week_df = df[df['week_start'] == current_week]

    weekly_hours = (
        week_df.groupby(['user_name', 'workstream_name', 'project_name'], as_index=False)
               .agg(hours_this_week=('time_spent', 'sum'))
    )

    latest_status = get_latest_status_map(df)
    result = weekly_hours.merge(
        latest_status,
        on=['user_name', 'workstream_name', 'project_name'],
        how='left',
    )

    result = result.sort_values(['user_name', 'workstream_name', 'project_name'])
    result = result.rename(columns={
        'user_name': 'Team Member',
        'workstream_name': 'Workstream',
        'project_name': 'Project Name',
        'hours_this_week': 'Hours (this week)',
        'latest_stage': 'Last thing did',
        'latest_status': 'Current Status',
    })

    if result.empty:
        st.markdown('_No hours logged this week._')
    else:
        with st.container():
            st.markdown(f"**{len(result)}** entries for {st.session_state.selected_week_label}")
            st.dataframe(result, use_container_width=True, height=min(900, 60 + 35 * len(result)))
    

    with st.container(border=True, key = "weekly_view_card2"):
        st.markdown("#### Executive Project Summary")
        st.markdown('**Operations Summary**')
        ops_summary = get_workstream_ops_summary(week_df)
        ops_summary = ops_summary.rename(columns={
            'workstream_name': 'Workstream',
            'total_touched': 'Projects Planned',
            'completed_count': 'Projects Completed',
            'all_projects': 'All Projects',
            'in_progress_projects': 'In Progress Projects',
        })
        if ops_summary.empty:
            st.markdown('_No hours logged this week._')
        else:
            st.dataframe(ops_summary)

        st.markdown("**WS1: Paddock Mapping and Digitisation**")
        paddock_summary = get_paddock_summary(week_df)
        if paddock_summary.empty:
                st.markdown('_No hours logged this week._')
        else:
            st.dataframe(paddock_summary)

        st.markdown("**R&D Summary**")
        rnd_summary = get_workstream_rnd_summary(week_df)
        if rnd_summary.empty:
            st.markdown('_No hours logged this week._')
        else:
            st.dataframe(rnd_summary)

    with st.container(border=True, key = "weekly_view_card3"):
        st.markdown("#### Team Bandwidth")
        st.markdown("Hours spent per team member, broken down by workstream.")

        bandwidth = get_user_workstream_hours(week_df)

        if bandwidth.empty:
            st.markdown('_No hours logged this week._')
        else:
            fig, ax = plt.subplots(figsize=(9, max(3, 0.6 * len(bandwidth))))
            fig.patch.set_alpha(0.0)
            ax.patch.set_alpha(0.0)

            bottom = pd.Series(0.0, index=bandwidth.index)
            for workstream in bandwidth.columns:
                values = bandwidth[workstream]
                ax.barh(bandwidth.index, values, left=bottom, label=workstream)
                bottom += values

            text_color = "#e8eef4"
            ax.set_xlabel('Hours', color=text_color)
            ax.set_ylabel('')
            ax.tick_params(colors=text_color)
            for spine in ax.spines.values():
                spine.set_color("#3a4a5a")

            legend = ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)
            legend.get_frame().set_alpha(0.0)
            for text in legend.get_texts():
                text.set_color(text_color)

            ax.invert_yaxis()
            fig.tight_layout()

            st.pyplot(fig, use_container_width=True)


page2()