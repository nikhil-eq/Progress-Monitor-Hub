import pandas as pd
import streamlit as st

from pathlib import Path

import plotly.graph_objects as go

from db import load_data, get_rework_summary

# --------------------------------------------------
#                  CONSTANTS
# --------------------------------------------------

workstreams_list_delivery = [
    'Initial Stratification - HIR',
    'Initial Stratification - NFMR',
    'Restratification - HIR',
    'Restratification - NFMR',
    'Restratification - Regen Check',
    'Restratification - AD',
    'Change Detection',
    'WS1: Paddock Mapping and Digitization',
    'WS2: AD Enhancements - Drivers of Change',
    'WS3: ALS-to-CPC',
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
#     COMPLETIONS-BY-MONTH TREND (stacked by workstream)
# --------------------------------------------------

# Distinct colors, one per workstream, reused every time the chart redraws
# so a given workstream is always the same color.
_COMPLETIONS_PALETTE = [
    '#E63946',  # Red
    '#F77F00',  # Orange
    '#F2C94C',  # Yellow
    '#2E7D32',  # Green
    '#00A896',  # Teal
    '#00B4D8',  # Cyan
    '#277DA1',  # Blue
    '#4361EE',  # Indigo
    '#7209B7',  # Purple
    '#C2185B',  # Magenta
    '#8D5524',  # Brown
    '#6C757D',  # Slate Gray
    '#FF6F61',  # Coral
]

def fig_completions_by_month_stacked(monthly_completions_df: pd.DataFrame, today: pd.Timestamp,
                                      months: int, workstreams_order: list) -> go.Figure:
    """
    Stacked bar: projects completed per month (last `months` months), each
    bar split into one segment per workstream, with the month's total
    labeled above the bar.
    """
    month_range = pd.period_range(end=today.to_period('M'), periods=months, freq='M')
    labels = [m.strftime('%b %Y') for m in month_range]

    d = monthly_completions_df.copy()
    d['month_period'] = pd.to_datetime(d['month']).dt.to_period('M')
    d = d[d['month_period'].isin(month_range)]

    counts = (
        d.groupby(['month_period', 'workstream_name'])
         .size()
         .unstack(fill_value=0)
         .reindex(index=month_range, fill_value=0)
    )

    # keep a stable, canonical workstream order; drop any with zero
    # completions across the whole window so the legend stays clean
    ordered_cols = [ws for ws in workstreams_order if ws in counts.columns]
    ordered_cols += [ws for ws in counts.columns if ws not in ordered_cols]
    counts = counts[ordered_cols]
    counts = counts.loc[:, counts.sum(axis=0) > 0]

    totals = counts.sum(axis=1)
    ws_colors = {ws: _COMPLETIONS_PALETTE[i % len(_COMPLETIONS_PALETTE)]
                 for i, ws in enumerate(counts.columns)}

    fig = go.Figure()
    for ws in counts.columns:
        vals = counts[ws]
        fig.add_trace(go.Bar(
            x=labels, y=vals, name=ws,
            marker_color=ws_colors[ws],
            text=[str(v) if v > 0 else '' for v in vals],
            textposition='inside', insidetextanchor='middle',
            textfont=dict(size=10, color='#0d1b0d'),
            hovertemplate=f'<b>{ws}</b><br>%{{x}}: %{{y}} completed<extra></extra>',
        ))

    # total label above each stacked bar
    fig.add_trace(go.Scatter(
        x=labels, y=totals, mode='text',
        text=[str(t) if t else '' for t in totals],
        textposition='top center',
        textfont=dict(color='#e8eef4', size=13, family='DejaVu Sans'),
        showlegend=False, hoverinfo='skip',
    ))

    fig.update_layout(
        barmode='stack',
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e8eef4'),
        height=440,
        margin=dict(l=8, r=8, t=40, b=8),
        bargap=0.35,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0,
                    font=dict(color='#e8eef4', size=9)),
    )
    fig.update_xaxes(type='category', gridcolor='#1a2a3a', color='#e8eef4')
    fig.update_yaxes(
        title='Projects completed', gridcolor='#1a2a3a', color='#e8eef4',
        range=[0, max(totals.max(), 1) * 1.3],
    )
    return fig


# --------------------------------------------------
#                   STYLING HELPER
# --------------------------------------------------

def render_bullet_table(df: pd.DataFrame):
    """Render a dataframe as HTML so that '\\n'-separated bullet lists inside
    cells show as real line breaks (st.dataframe collapses newlines)."""
    display_df = df.copy()
    for col in display_df.columns:
        if display_df[col].dtype == object:
            display_df[col] = display_df[col].astype(str).str.replace("\n", "<br>")

    html = display_df.to_html(escape=False, index=False, classes="bullet-table", border=0)
    st.markdown(html, unsafe_allow_html=True)

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

# --------------------------------------------------
#                       PAGE
# --------------------------------------------------

def page4():
    inject_css()

    with st.container(border=True):
        st.markdown('#### Delivered - Since Inception')

    summary_df, project_status_df, monthly_completions_df = load_workstream_data()

    st.markdown("#### Completions by month")

    months_selected = st.slider(
        "Months to show", min_value=3, max_value=24, value=6, step=1,
        key='delivered_completion_months',
    )
    st.markdown(
        f"Projects completed in each of the last {months_selected} months, split by workstream. "
        f"The number above each bar is that month's total."
    )

    if monthly_completions_df.empty:
        st.markdown('_No completed projects yet._')
    else:
        today = pd.Timestamp.now(tz='Asia/Kolkata').tz_localize(None).normalize()
        st.plotly_chart(
            fig_completions_by_month_stacked(
                monthly_completions_df, today, months_selected, workstreams_list_delivery
            ),
            use_container_width=True,
            key=f"delivered_completions_trend_{months_selected}",
        )

    with st.expander(label = 'View Total Number of Projects Delivered'):
        st.markdown('Number of **Projects Completed (Lifetime)** in Each of the Workstreams')

        st.dataframe(summary_df, use_container_width=True,
                     height=min(900, 60 + 35 * len(summary_df)))
        
    with st.expander('⚠️ Projects Flagged for Rework'):
            st.markdown(
                "A project/stage is flagged here if work returned to a stage the team had "
                "already moved past (e.g. sent back from Peer Review to Processing)."
            )
            
            df = load_data()
            
            rework_summary = get_rework_summary(df)
            rework_summary = rework_summary.rename(columns={
                'workstream_name': 'Workstream',
                'project_name': 'Project Name',
                'reworked_stages': 'Stage(s) Reworked',
                'rework_count': '# Rework Events',
                'last_rework_date': 'Most Recent Rework',
            })
            if rework_summary.empty:
                st.markdown('_No rework detected across any workstream/project so far. 🎉_')
            else:
                rework_summary['Most Recent Rework'] = pd.to_datetime(
                    rework_summary['Most Recent Rework']
                ).dt.strftime('%d %b %Y')
                rework_summary = rework_summary.sort_values('Most Recent Rework', ascending=False)
                st.dataframe(rework_summary, use_container_width=True,
                             height=min(500, 60 + 35 * len(rework_summary)))


    # ------------------------------------------------------------------
    #  Panels: completed projects by month, broken out per workstream
    # ------------------------------------------------------------------
    st.markdown("&nbsp;")  # spacer between the summary table and the panels below
    st.markdown("#### Completed Projects by Workstream")

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