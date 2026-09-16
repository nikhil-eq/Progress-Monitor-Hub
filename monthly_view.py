import pandas as pd
import streamlit as st

from pathlib import Path

import plotly.graph_objects as go

from db import load_data

# --------------------------------------------------
#                  CONSTANTS
# --------------------------------------------------

# Stage name(s) that should never count toward a project being "completed" —
# a peer reviewer marking their own review step complete doesn't mean the
# underlying project is done, and shouldn't credit them as the completer.
NON_COMPLETING_STAGES = {'peer review'}

# CHANGE THIS if your time-tracking column has a different name
TIME_COLUMN = 'time_spent'

workstreams_list_delivery = [
    'Initial Stratification - HIR',
    'Initial Stratification - NFMR',
    'Restratification - HIR',
    'Restratification - NFMR',
    'Restratification - Regen Check',
    'Restratification - AD',
    'Change Detection',
    'WS1:Paddock Mapping and Digitization',
    'Fire Impact Assessment',
    'Grid Creation',
    'Spatial Data Cleaning and Ingestion',
    'AD Survey Packages',
    'Field Survey Packages',
    'Adhoc Analysis',
    'Carbon Plus',
]


# --------------------------------------------------
#          DATA-SHAPING FUNCTIONS (updated)
# --------------------------------------------------

def get_monthly_project_status(month_df: pd.DataFrame):
    """
    Returns (summary, detail):

    summary: one row per workstream for the selected month — all projects
    touched (each annotated with who completed it, or who last worked on it
    if still in progress), completed count, total projects touched, who
    completed anything in that workstream, and total time spent.

    detail: the underlying per-(workstream, project) rows used to build the
    summary — kept around so charts can be built directly off it (e.g. a
    per-person completions leaderboard) without re-deriving completed_by.
    """
    month_df = month_df.copy()
    month_df['current_status'] = month_df['current_status'].astype(str).str.strip()

    # latest known status/activity per project this month, and who that was
    latest = (
        month_df.sort_values('date')
                .groupby(['workstream_name', 'project_name'], as_index=False)
                .last()[['workstream_name', 'project_name', 'current_status', 'user_name', 'date']]
                .rename(columns={'user_name': 'last_worked_by', 'date': 'last_activity_date'})
    )

    # who completed each project — the most recent entry (this month) where
    # the status was actually marked 'completed'. Peer-review rows are
    # excluded here: finishing your own peer-review step shouldn't mark the
    # project completed, or credit the reviewer as the person who completed it.
    if 'stage' in month_df.columns:
        completable = month_df[
            ~month_df['stage'].astype(str).str.strip().str.lower().isin(NON_COMPLETING_STAGES)
        ]
    else:
        completable = month_df

    completed_rows = completable[completable['current_status'].str.lower() == 'completed']
    if not completed_rows.empty:
        completed_latest = (
            completed_rows.sort_values('date')
                          .groupby(['workstream_name', 'project_name'], as_index=False)
                          .last()[['workstream_name', 'project_name', 'user_name', 'date']]
                          .rename(columns={'user_name': 'completed_by', 'date': 'completed_date'})
        )
    else:
        completed_latest = pd.DataFrame(
            columns=['workstream_name', 'project_name', 'completed_by', 'completed_date']
        )

    detail = latest.merge(completed_latest, on=['workstream_name', 'project_name'], how='left')
    detail['is_completed'] = detail['completed_by'].notna()

    def make_display(row):
        if row['is_completed']:
            return f"{row['project_name']} ✅ completed by {row['completed_by']}"
        status_label = row['current_status']
        if status_label.strip().lower() == 'completed':
            # the most recent row says 'completed', but it was a non-counting
            # stage (e.g. peer review) — don't show a misleading label
            status_label = 'in progress'
        return f"{row['project_name']} — {status_label} (last: {row['last_worked_by']})"

    detail['project_display'] = detail.apply(make_display, axis=1)
    detail = detail.sort_values(['workstream_name', 'project_name'])

    # total time actually logged against each project this month (sum of ALL
    # entries, not just the latest one — the previous version only summed
    # each project's single most-recent row, which undercounted hours)
    if TIME_COLUMN in month_df.columns:
        time_per_project = (
            month_df.groupby(['workstream_name', 'project_name'], as_index=False)[TIME_COLUMN]
                    .sum()
        )
        detail = detail.merge(time_per_project, on=['workstream_name', 'project_name'], how='left')
    else:
        detail[TIME_COLUMN] = 0.0

    agg_dict = {
        'project_names': ('project_display', lambda s: ' • '.join(s)),
        'completed_count': ('is_completed', 'sum'),
        'total_projects': ('project_name', 'count'),
        'completed_by_list': (
            'completed_by',
            lambda s: ', '.join(sorted(set(s.dropna()))) if s.notna().any() else '—'
        ),
        'total_time': (TIME_COLUMN, 'sum'),
    }

    summary = (
        detail.groupby('workstream_name')
              .agg(**agg_dict)
              .reset_index()
    )

    summary['workstream_name'] = pd.Categorical(
        summary['workstream_name'], categories=workstreams_list_delivery, ordered=True
    )
    summary = summary.sort_values('workstream_name').reset_index(drop=True)
    return summary, detail


# --------------------------------------------------
#                   CHART BUILDERS
# --------------------------------------------------

def build_workstream_completion_figure(detail: pd.DataFrame) -> go.Figure:
    """
    Horizontal stacked bar: for every workstream touched this month, bar
    length is HOURS spent (completed vs in-progress), while the label and
    hover information show PROJECT COUNT.
    """
    scoped = detail.copy()
    scoped['workstream_name'] = pd.Categorical(
        scoped['workstream_name'],
        categories=workstreams_list_delivery,
        ordered=True
    )

    hours = (
        scoped.groupby(
            ['workstream_name', 'is_completed'],
            observed=False
        )[TIME_COLUMN]
        .sum()
        .unstack(fill_value=0.0)
    )

    counts = (
        scoped.groupby(
            ['workstream_name', 'is_completed'],
            observed=False
        )['project_name']
        .nunique()
        .unstack(fill_value=0)
    )

    for col in (True, False):
        if col not in hours.columns:
            hours[col] = 0.0
        if col not in counts.columns:
            counts[col] = 0

    hours = hours.sort_index()
    counts = counts.reindex(hours.index)

    keep_mask = (hours[True] + hours[False]) > 0
    hours = hours[keep_mask]
    counts = counts[keep_mask]

    hours = hours.iloc[::-1]
    counts = counts.iloc[::-1]

    workstream_labels = hours.index.astype(str)

    fig = go.Figure()

    # Completed
    fig.add_trace(go.Bar(
        y=workstream_labels,
        x=hours[True],
        name='Completed',
        orientation='h',
        marker_color='#2ecc71',

        # Project count displayed inside the bar
        text=[f"{c}" if c > 0 else "" for c in counts[True]],
        textposition='inside',
        insidetextanchor='middle',
        textfont=dict(color='#0d1b0d', size=11),

        # Per-workstream project count
        customdata=counts[True].to_numpy(),

        hovertemplate=(
            "<b>%{y}</b><br>"
            "Completed projects: %{customdata}<br>"
            "Hours: %{x:.1f}"
            "<extra></extra>"
        ),
    ))

    # In Progress
    fig.add_trace(go.Bar(
        y=workstream_labels,
        x=hours[False],
        name='In Progress',
        orientation='h',
        marker_color='#4a5a6a',

        # Project count displayed inside the bar
        text=[f"{c}" if c > 0 else "" for c in counts[False]],
        textposition='inside',
        insidetextanchor='middle',
        textfont=dict(color='#e8eef4', size=11),

        # Per-workstream project count
        customdata=counts[False].to_numpy(),

        hovertemplate=(
            "<b>%{y}</b><br>"
            "In-progress projects: %{customdata}<br>"
            "Hours: %{x:.1f}"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        barmode='stack',
        title=dict(
            text='Completed vs In Progress',
            font=dict(color='#e8eef4', size=16)
        ),
        xaxis=dict(
            title='Hours spent',
            color='#e8eef4',
            gridcolor='#1a2a3a',
            rangemode='tozero'
        ),
        yaxis=dict(
            title='',
            color='#e8eef4',
            automargin=True
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            x=0,
            font=dict(color='#e8eef4')
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=max(360, 42 * len(workstream_labels)),
        margin=dict(l=10, r=20, t=70, b=40),
    )

    return fig

def build_top_completers_figure(detail: pd.DataFrame, month_df: pd.DataFrame) -> go.Figure | None:
    """
    Horizontal bar: bar length is total hours each person logged this month;
    the label drawn inside the bar is how many projects they completed.
    Ranked by hours (longest bar on top). Returns None if nobody completed
    anything (caller should handle that).
    """
    completed = detail[detail['is_completed']]
    if completed.empty:
        return None

    completed_counts = completed.groupby('completed_by').size()

    hours_by_user = month_df.groupby('user_name')[TIME_COLUMN].sum()
    hours = hours_by_user.reindex(completed_counts.index).fillna(0.0)

    order = hours.sort_values(ascending=True).index
    hours = hours.loc[order]
    completed_counts = completed_counts.loc[order]

    fig = go.Figure(go.Bar(
        x=hours.values, y=hours.index, orientation='h',
        marker_color='#4da3ff',
        text=[f"{c} completed" for c in completed_counts.values],
        textposition='inside', insidetextanchor='middle',
        textfont=dict(color='#f5f8ff', size=11),
        hoverinfo="skip",
    ))
    max_val = max(hours.values.max(), 1)
    fig.update_layout(
        title=dict(text='Hours | Projects Completed | Individual Memebers', font=dict(color='#e8eef4', size=16)),
        xaxis=dict(title='Hours spent', color='#e8eef4', gridcolor='#1a2a3a',
                   rangemode='tozero', range=[0, max_val * 1.15]),
        yaxis=dict(title='', color='#e8eef4', automargin=True),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=max(300, 42 * len(hours)),
        margin=dict(l=10, r=30, t=60, b=40),
        showlegend=False,
    )
    return fig


# --------------------------------------------------
#                   STYLING HELPER
# --------------------------------------------------

st.markdown("""
    <style>
    div.st-key-monthly_view_card1 {
        background-color: #ffffff00 !important;
        border-radius: 8px;
        padding: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    div.st-key-monthly_view_card2 {
        background-color: #004f72 !important;
        border-radius: 8px;
        padding: 1rem;
    }
    </style>
""", unsafe_allow_html=True)



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

    with st.container(border=True, key = 'monthly_view_card1'):
        st.markdown('#### Monthly Recap')

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

    summary, detail = get_monthly_project_status(month_df)
    result = summary.rename(columns={
        'workstream_name': 'Workstream',
        'project_names': 'Project Name',
        'completed_count': 'Completed Projects Count',
        'total_projects': 'Total Projects Touched',
        'completed_by_list': 'Completed By',
        'total_time': 'Time Spent (hrs)',
    })

    with st.container(border=True, key = 'monthly_view_card2'):
        completed_sum = result['Completed Projects Count'].sum() if not result.empty else 0
        touched_sum = result['Total Projects Touched'].sum() if not result.empty else 0
        time_sum = result['Time Spent (hrs)'].sum() if not result.empty else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Completed", f"{int(completed_sum)}")
        col2.metric("Touched", f"{int(touched_sum)}")
        col3.metric("Total Hours", f"{time_sum:,.1f}")

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        if result.empty:
            st.markdown('_No activity logged this month._')
        else:
            st.plotly_chart(
                build_workstream_completion_figure(detail),
                use_container_width=True,
                key=f"monthly_completion_{current_month}",
            )
    with chart_col2:
        leaderboard_fig = build_top_completers_figure(detail, month_df) if not detail.empty else None
        if leaderboard_fig is None:
            st.markdown('_Nobody completed a project this month yet._')
        else:
            st.plotly_chart(
                leaderboard_fig,
                use_container_width=True,
                key=f"monthly_leaderboard_{current_month}",
            )

    with st.expander("View Detailed Table"):
        st.dataframe(
            result[['Workstream', 'Project Name', 'Completed By', 'Completed Projects Count',
                    'Total Projects Touched', 'Time Spent (hrs)']],
            use_container_width=True,
            height=min(900, 60 + 35 * len(result)),
        )

page3()