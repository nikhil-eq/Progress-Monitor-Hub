import pandas as pd
import streamlit as st

from pathlib import Path

import io

import matplotlib as mpl
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

rnd_list = [
    'Research and Development',
    'Productivity & Enablement',
    'WS1:Paddock Mapping and Digitization'
]


# --------------------------------------------------
#              HD CHART RENDERING SETTINGS
# --------------------------------------------------

HD_CHART_DPI = 1000      # export resolution (use 600 for print/PDF reports)
HD_CHART_FORMAT = 'png' # switch to 'svg' for infinitely crisp vector graphics


def setup_hd_matplotlib():
    """Global matplotlib tweaks so every chart is anti-aliased, well-spaced
    and exported at print resolution."""
    mpl.rcParams.update({
        # resolution / crispness
        'figure.dpi': 120,
        'savefig.dpi': HD_CHART_DPI,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.15,
        'text.antialiased': True,
        'lines.antialiased': True,
        'patch.antialiased': True,
        # typography
        'font.family': 'DejaVu Sans',
        'font.size': 11,
        'axes.titlesize': 15,
        'axes.titleweight': 'bold',
        'axes.labelsize': 12,
        'xtick.labelsize': 10.5,
        'ytick.labelsize': 10.5,
        'legend.fontsize': 9.5,
        # dark-theme aware defaults
        'text.color': '#e8eef4',
        'axes.labelcolor': '#e8eef4',
        'xtick.color': '#e8eef4',
        'ytick.color': '#e8eef4',
        'axes.edgecolor': '#3a4a5a',
        'svg.fonttype': 'none',  # keep real text in SVG exports (selectable/crisp)
    })


setup_hd_matplotlib()


def render_figure_hd(fig, transparent=True):
    """Save the figure at high DPI (or as vector SVG) into a buffer and
    display THAT, so Streamlit never upscales a blurry low-res PNG."""
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format=HD_CHART_FORMAT,
        dpi=HD_CHART_DPI,
        transparent=transparent,
        bbox_inches='tight',
        pad_inches=0.15,
    )
    buf.seek(0)
    st.image(buf, use_container_width=True)


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
    One row per workstream (or, for Adhoc Analysis specifically, one row per
    stage under it — labeled 'Adhoc Analysis - <stage>'): how many distinct
    projects have been touched, how many are completed, and a bullet-point
    breakdown of project names.
    """
    scoped = df[df['workstream_name'].isin(workstreams_list_delivery)].copy()
    scoped['current_status'] = scoped['current_status'].str.strip().str.lower()
    scoped['stage'] = scoped['stage'].str.strip()

    # display-only grouping key: split Adhoc Analysis out by stage,
    # leave every other workstream as-is
    scoped['display_workstream'] = scoped.apply(
        lambda r: f"Adhoc Analysis - {r['stage']}" if r['workstream_name'] == 'Adhoc Analysis'
                  else r['workstream_name'],
        axis=1,
    )

    # latest known status per (display_workstream, project) — not per user,
    # since this view is about project completion, not who logged it
    project_status = (
        scoped.sort_values('date')
              .groupby(['display_workstream', 'project_name'], as_index=False)
              .last()[['display_workstream', 'project_name', 'current_status']]
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
        project_status.groupby('display_workstream')
                       .apply(build_row, include_groups=False)
                       .reset_index()
    )
    summary = summary.rename(columns={'display_workstream': 'workstream_name'})

    # keep the original ordering from workstreams_list_delivery, but let any
    # 'Adhoc Analysis - <stage>' variants sit where 'Adhoc Analysis' used to be
    def sort_key(name):
        base = name.split(' - ')[0] if name.startswith('Adhoc Analysis') else name
        try:
            base_rank = workstreams_list_delivery.index(base)
        except ValueError:
            base_rank = len(workstreams_list_delivery)
        return (base_rank, name)

    summary = summary.sort_values(by='workstream_name', key=lambda col: col.map(sort_key))
    summary = summary.reset_index(drop=True)
    return summary


def get_paddock_als_cpc_summary(df: pd.DataFrame) -> pd.DataFrame:
    scoped = df[df['workstream_name'].isin(['WS1:Paddock Mapping and Digitization', 'WS3:ALS-to-CPC'])].copy()
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
        summary['workstream_name'], categories=['WS1:Paddock Mapping and Digitization', 'WS3:ALS-to-CPC'], ordered=True
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
    scoped = df[df['workstream_name'].isin(rnd_list)].copy()
    scoped = scoped[~scoped['stage'].isin({'Meetings', 'Debugging'})]

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

    # Guard: nothing left to summarize this week
    if scoped.empty:
        return pd.DataFrame(columns=['Workstream', 'Progress'])

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
    summary = summary.rename(columns={'stage': 'Workstream', 'detail': 'Progress'})
    return summary


def get_user_workstream_hours(week_df: pd.DataFrame) -> pd.DataFrame:
    """
    Hours per (user, workstream) for the given week, across ALL workstreams
    (no filtering to workstreams_list_delivery — Productivity & Enablement, R&D, etc. included).
    """
    week_df['time_spent'] = pd.to_numeric(
                            week_df['time_spent'],
                            errors='coerce'
                        ).fillna(0)
    hours = (
        week_df.groupby(['user_name', 'workstream_name'], as_index=False)
               .agg(hours=('time_spent', 'sum'))
    )
    pivot = hours.pivot(index='user_name', columns='workstream_name', values='hours').fillna(0)
    return pivot

def get_user_stage_workstream_hours(week_df: pd.DataFrame) -> dict:
    """
    For each user: a pivot table of workstream_name (rows) x stage (columns),
    with hours as values — used to build one stacked bar chart per user,
    where each bar (workstream) is broken down by the stages worked on.
    """
    week_df = week_df.copy()
    week_df['time_spent'] = pd.to_numeric(week_df['time_spent'], errors='coerce').fillna(0)

    hours = (
        week_df.groupby(['user_name', 'workstream_name', 'stage'], as_index=False)
               .agg(hours=('time_spent', 'sum'))
    )

    user_pivots = {}
    for user in sorted(hours['user_name'].dropna().unique()):
        user_data = hours[hours['user_name'] == user]
        pivot = user_data.pivot(index='workstream_name', columns='stage', values='hours').fillna(0)
        user_pivots[user] = pivot

    return user_pivots


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
        background-color: #ffffff00 !important;
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


def page2():
    inject_css()

    with st.container(border=True, key = "weekly_view_card"):
        st.markdown('#### Weekly Snapshot')

        df = load_data()

        # Convert to datetime
        df['week_start'] = pd.to_datetime(df['week_start'])

        all_weeks = df['week_start'].dropna().unique()

        # Ascending order, purely to compute correct "Week N" numbering
        weeks_asc = sorted(all_weeks)

        # Descending order, for how the dropdown is displayed (latest first)
        weeks_desc = sorted(all_weeks, reverse=True)

        # Week number resets for each month, counting forward chronologically
        week_labels = {}
        month_week_counter = {}

        for w in weeks_asc:
            ts = pd.Timestamp(w)
            month_key = (ts.year, ts.month)

            month_week_counter[month_key] = month_week_counter.get(month_key, 0) + 1

            week_labels[w] = (
                f"Week {month_week_counter[month_key]}: "
                f"{ts.strftime('%d %b %Y')}"
            )

        label_to_week = {v: k for k, v in week_labels.items()}

        # Dropdown still shows latest week first, but labels are now chronological
        week_label_options = [week_labels[w] for w in weeks_desc]

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
    
    with st.expander('View Logs'):

        if result.empty:
            st.markdown('_No hours logged this week._')
        else:
            with st.container():
                st.dataframe(result, use_container_width=True, height=min(900, 60 + 35 * len(result)))
            
    with st.container(border=True, key="weekly_view_card4"):
        st.markdown("#### Individual Workstream Breakdown")
        st.markdown("Hours per workstream, broken down by stage worked on - one chart per team member.")

        user_pivots = get_user_stage_workstream_hours(week_df)

        if not user_pivots:
            st.markdown('_No hours logged this week._')
        else:
            # build one shared color map for stages, so the same stage
            # always gets the same color across all four charts
            all_stages = sorted({s for pivot in user_pivots.values() for s in pivot.columns})
            cmap = plt.colormaps.get_cmap('tab20')
            stage_colors = {stage: cmap(i / max(len(all_stages) - 1, 1)) for i, stage in enumerate(all_stages)}

            n_users = len(user_pivots)
            n_cols = 2 if n_users > 1 else 1          # two charts per row
            n_rows = (n_users + n_cols - 1) // n_cols
            fig, axes = plt.subplots(n_rows, n_cols, figsize=(5.5 * n_cols, 5.2 * n_rows), sharey=True)
            fig.patch.set_alpha(0.0)

            axes = list(axes.flat) if n_rows * n_cols > 1 else [axes]
            for unused_ax in axes[n_users:]:
                unused_ax.axis('off')                 # hide empty slot on the last row

            text_color = "#e8eef4"

            for ax, (user, pivot) in zip(axes, user_pivots.items()):
                ax.patch.set_alpha(0.0)

                bottom = pd.Series(0.0, index=pivot.index)
                for stage in pivot.columns:
                    values = pivot[stage]
                    ax.bar(pivot.index, values, bottom=bottom, label=stage, color=stage_colors[stage], edgecolor="#0d1b2641", linewidth=0.5)
                    bottom += values

                ax.grid(axis='x', visible=False)
                ax.set_title(user, color=text_color, fontsize=13, fontweight='bold')
                ax.set_xlabel('')
                ax.tick_params(colors=text_color, labelrotation=90)
                for spine in ax.spines.values():
                    spine.set_color("#3a4a5a00")

            axes[0].set_ylabel('Hours', color=text_color)
            axes[0].tick_params(axis='y', colors=text_color)

            # single shared legend for the whole figure, not per subplot
            handles = [plt.Rectangle((0, 0), 1, 1, color=stage_colors[s]) for s in all_stages]
            legend = fig.legend(handles, all_stages, loc='upper center',
                                 bbox_to_anchor=(0.5, -0.05), ncol=4, fontsize=8)
            legend.get_frame().set_alpha(0.0)
            for text in legend.get_texts():
                text.set_color(text_color)

            fig.tight_layout()
            render_figure_hd(fig)
    
    with st.expander('View Executive Project Summary'):
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
                
            st.markdown("**R&D Summary**")
            
            st.markdown('Quantitative')
            
            paddock_summary = get_paddock_als_cpc_summary(week_df)
            if paddock_summary.empty:
                    st.markdown('_No hours logged this week._')
            else:
                st.dataframe(paddock_summary)
            
            st.markdown('Qualitative')

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
            fig, ax = plt.subplots(figsize=(10, max(3.5, 0.7 * len(bandwidth))))
            fig.patch.set_alpha(0.0)
            ax.patch.set_alpha(0.0)

            bottom = pd.Series(0.0, index=bandwidth.index)
            for workstream in bandwidth.columns:
                values = bandwidth[workstream]
                ax.barh(bandwidth.index, values, left=bottom, label=workstream, edgecolor="#0d1b2600", linewidth=0.5)
                bottom += values

            text_color = "#e8eef4"
            ax.grid(axis='y', visible=False)
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

            render_figure_hd(fig)


import pandas as pd
import streamlit as st

from pathlib import Path

import io

import matplotlib as mpl
import matplotlib.pyplot as plt

import re

import plotly.graph_objects as go
import plotly.express as px
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import colorsys

from db import load_data, compute_rework_flags, get_rework_summary

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

rnd_list = [
    'Research and Development',
    'Productivity & Enablement',
    'WS1:Paddock Mapping and Digitization'
]

# Fixed weekly capacity used for the "allotted vs actual" chart titles
# (e.g. "Nikhil — 32.0/40 hours"). Change here if this ever needs to vary.
ALLOTTED_HOURS_PER_WEEK = 40

# --------------------------------------------------
#   "Where the hours went this week" chart (from Home)
# --------------------------------------------------
# Same category split/colors as the Home page, so the two stay consistent.

CAT_TEAL = '#5eead4'
CAT_VIOLET = '#a78bfa'
CAT_SLATE = '#64748b'
CATEGORY_COLORS = {'Delivery': CAT_TEAL, 'R&D': CAT_VIOLET, 'Enablement & other': CAT_SLATE}


def _norm_ws(name: str) -> str:
    """Some rows are stored as 'WS1:Paddock' and others as 'WS1: Paddock'.
    Normalise both sides so they group together."""
    return re.sub(r':\s*', ': ', str(name))


_DELIVERY_NORM = {_norm_ws(w) for w in workstreams_list_delivery}


def categorize_hours(df: pd.DataFrame) -> pd.DataFrame:
    """Tag each row with a 'category' (Delivery / R&D / Enablement & other)
    and a normalised workstream name, mirroring the Home page's logic."""
    d = df.copy()
    d['workstream_name'] = d['workstream_name'].astype(str).str.strip().map(_norm_ws)
    d['time_spent'] = pd.to_numeric(d.get('time_spent', 0.0), errors='coerce').fillna(0.0)

    work_type = d['work_type'].astype(str).str.strip().str.lower() if 'work_type' in d.columns else ''

    in_delivery = d['workstream_name'].isin(_DELIVERY_NORM)
    is_rnd = (work_type == 'r&d') | (d['workstream_name'].str.lower() == 'research and development')

    d['category'] = 'Enablement & other'
    d.loc[in_delivery, 'category'] = 'Delivery'
    d.loc[is_rnd, 'category'] = 'R&D'
    return d


def fig_workstream_hours(week_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar of hours logged this week per workstream (top 8,
    everything else rolled up), colored by category."""
    d = categorize_hours(week_df)

    g = (d.groupby('workstream_name')
           .agg(hours=('time_spent', 'sum'), cat=('category', 'first'))
           .query('hours > 0').sort_values('hours', ascending=False))

    names = list(g.index[:8])
    values = list(g['hours'][:8])
    colors = [CATEGORY_COLORS[c] for c in g['cat'][:8]]
    rest = g['hours'][8:].sum()
    if rest > 0:
        names.append('Everything else')
        values.append(rest)
        colors.append(CAT_SLATE)

    fig = go.Figure(go.Bar(
        x=values, y=names, orientation='h', marker_color=colors,
        text=[f'{v:.1f}' for v in values], textposition='outside', cliponaxis=False,
        hovertemplate='<b>%{y}</b><br>%{x:.1f} h<extra></extra>',
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e8eef4'),
        height=max(240, 40 * len(names) + 60),
        margin=dict(l=8, r=8, t=28, b=8),
        bargap=0.3,
    )
    fig.update_xaxes(gridcolor='#1a2a3a', zeroline=False, color='#e8eef4',
                      range=[0, max(values) * 1.2], title='Hours')
    fig.update_yaxes(gridcolor='#1a2a3a', zeroline=False, color='#e8eef4',
                      autorange='reversed', automargin=True)
    return fig


# --------------------------------------------------
#              HD CHART RENDERING SETTINGS
# --------------------------------------------------

HD_CHART_DPI = 1000      # export resolution (use 600 for print/PDF reports)
HD_CHART_FORMAT = 'png' # switch to 'svg' for infinitely crisp vector graphics


def setup_hd_matplotlib():
    """Global matplotlib tweaks so every chart is anti-aliased, well-spaced
    and exported at print resolution."""
    mpl.rcParams.update({
        # resolution / crispness
        'figure.dpi': 120,
        'savefig.dpi': HD_CHART_DPI,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.15,
        'text.antialiased': True,
        'lines.antialiased': True,
        'patch.antialiased': True,
        # typography
        'font.family': 'DejaVu Sans',
        'font.size': 11,
        'axes.titlesize': 15,
        'axes.titleweight': 'bold',
        'axes.labelsize': 12,
        'xtick.labelsize': 10.5,
        'ytick.labelsize': 10.5,
        'legend.fontsize': 9.5,
        # dark-theme aware defaults
        'text.color': '#e8eef4',
        'axes.labelcolor': '#e8eef4',
        'xtick.color': '#e8eef4',
        'ytick.color': '#e8eef4',
        'axes.edgecolor': '#3a4a5a',
        'svg.fonttype': 'none',  # keep real text in SVG exports (selectable/crisp)
    })


setup_hd_matplotlib()


def render_figure_hd(fig, transparent=True):
    """Save the figure at high DPI (or as vector SVG) into a buffer and
    display THAT, so Streamlit never upscales a blurry low-res PNG."""
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format=HD_CHART_FORMAT,
        dpi=HD_CHART_DPI,
        transparent=transparent,
        bbox_inches='tight',
        pad_inches=0.15,
    )
    buf.seek(0)
    st.image(buf, use_container_width=True)


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
    One row per workstream (or, for Adhoc Analysis specifically, one row per
    stage under it — labeled 'Adhoc Analysis - <stage>'): how many distinct
    projects have been touched, how many are completed, and a bullet-point
    breakdown of project names.
    """
    scoped = df[df['workstream_name'].isin(workstreams_list_delivery)].copy()
    scoped['current_status'] = scoped['current_status'].str.strip().str.lower()
    scoped['stage'] = scoped['stage'].str.strip()

    # display-only grouping key: split Adhoc Analysis out by stage,
    # leave every other workstream as-is
    scoped['display_workstream'] = scoped.apply(
        lambda r: f"Adhoc Analysis - {r['stage']}" if r['workstream_name'] == 'Adhoc Analysis'
                  else r['workstream_name'],
        axis=1,
    )

    # latest known status per (display_workstream, project) — not per user,
    # since this view is about project completion, not who logged it
    project_status = (
        scoped.sort_values('date')
              .groupby(['display_workstream', 'project_name'], as_index=False)
              .last()[['display_workstream', 'project_name', 'current_status']]
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
        project_status.groupby('display_workstream')
                       .apply(build_row, include_groups=False)
                       .reset_index()
    )
    summary = summary.rename(columns={'display_workstream': 'workstream_name'})

    # keep the original ordering from workstreams_list_delivery, but let any
    # 'Adhoc Analysis - <stage>' variants sit where 'Adhoc Analysis' used to be
    def sort_key(name):
        base = name.split(' - ')[0] if name.startswith('Adhoc Analysis') else name
        try:
            base_rank = workstreams_list_delivery.index(base)
        except ValueError:
            base_rank = len(workstreams_list_delivery)
        return (base_rank, name)

    summary = summary.sort_values(by='workstream_name', key=lambda col: col.map(sort_key))
    summary = summary.reset_index(drop=True)
    return summary


def get_paddock_als_cpc_summary(df: pd.DataFrame) -> pd.DataFrame:
    scoped = df[df['workstream_name'].isin(['WS1:Paddock Mapping and Digitization', 'WS3:ALS-to-CPC'])].copy()
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
        summary['workstream_name'], categories=['WS1:Paddock Mapping and Digitization', 'WS3:ALS-to-CPC'], ordered=True
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
    scoped = df[df['workstream_name'].isin(rnd_list)].copy()
    scoped = scoped[~scoped['stage'].isin(['Meetings', 'Debugging', 'House Help', 'Training / KT Given', 'Training / KT Received'])]

    scoped['stage'] = scoped['stage'].str.strip()
    scoped['rnd_explaination'] = scoped['rnd_explaination'].astype(str).str.strip()

    paddock_stage_names = {'Processing', 'Completed'}
    scoped = scoped[~scoped['stage'].isin(paddock_stage_names)]

    stage_display_names = {
        'iMAD': 'iMAD: Change Detection',
        'WS3:ALS-to-CPC': 'WS3: ALS-to-CPC',
        'Fire Impact Assessment': 'Fire Impact Assessment',
        'WS2:AD Enhancements & driver of changes': 'WS2:AD Enhancements & driver of changes',
    }
    scoped['stage'] = scoped['stage'].replace(stage_display_names)

    if scoped.empty:
        return pd.DataFrame(columns=['Workstream', 'Progress'])

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
    summary = summary.rename(columns={'stage': 'Workstream', 'detail': 'Progress'})
    return summary


def get_user_workstream_hours(week_df: pd.DataFrame) -> pd.DataFrame:
    """
    Hours per (user, workstream) for the given week, across ALL workstreams
    (no filtering to workstreams_list_delivery — Productivity & Enablement, R&D, etc. included).
    """
    week_df['time_spent'] = pd.to_numeric(
                            week_df['time_spent'],
                            errors='coerce'
                        ).fillna(0)
    hours = (
        week_df.groupby(['user_name', 'workstream_name'], as_index=False)
               .agg(hours=('time_spent', 'sum'))
    )
    pivot = hours.pivot(index='user_name', columns='workstream_name', values='hours').fillna(0)
    return pivot


def get_user_stage_workstream_hours(week_df: pd.DataFrame) -> dict:
    """
    For each user: a pivot table of workstream_name (rows) x stage (columns),
    with hours as values — used to build one chart per user, where each bar
    (workstream) is split into segments for the stages worked on within it.
    """
    week_df = week_df.copy()
    week_df['time_spent'] = pd.to_numeric(week_df['time_spent'], errors='coerce').fillna(0)

    hours = (
        week_df.groupby(['user_name', 'workstream_name', 'stage'], as_index=False)
               .agg(hours=('time_spent', 'sum'))
    )

    user_pivots = {}
    for user in sorted(hours['user_name'].dropna().unique()):
        user_data = hours[hours['user_name'] == user]
        pivot = user_data.pivot(index='workstream_name', columns='stage', values='hours').fillna(0)
        # drop workstreams with no hours at all, keep a stable, largest-first row order
        pivot = pivot[pivot.sum(axis=1) > 0]
        pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
        user_pivots[user] = pivot

    return user_pivots


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


GOLDEN_RATIO_CONJUGATE = 0.618033988749895


def build_workstream_hue_map(user_pivots: dict) -> dict:
    """
    One distinct base hue per workstream, shared across every person's chart
    so 'Grid Creation' (say) is always the same base color no matter whose
    chart it appears in. Hues are spaced using the golden-angle trick so
    adjacent workstreams (alphabetically) don't end up as near-duplicate
    colors even when there are many of them.
    """
    all_workstreams = sorted({ws for pivot in user_pivots.values() for ws in pivot.index})
    hues = {}
    h = 0.05  # start slightly off pure red
    for ws in all_workstreams:
        hues[ws] = h
        h = (h + GOLDEN_RATIO_CONJUGATE) % 1.0
    return hues


def stage_color_ramp(base_hue: float, n: int) -> list:
    """
    n colors going light -> dark within a single hue, used for the stage
    segments stacked inside ONE workstream's bar. Each workstream has its
    own base hue (from build_workstream_hue_map), so every bar's ramp is a
    different color family, light-to-dark within itself.
    """
    if n <= 0:
        return []
    if n == 1:
        r, g, b = colorsys.hls_to_rgb(base_hue, 0.48, 0.55)
        return [mcolors.to_hex((r, g, b))]
    colors = []
    for i in range(n):
        lightness = 0.80 - 0.44 * i / (n - 1)  # light (large segment) -> dark (small segment)
        r, g, b = colorsys.hls_to_rgb(base_hue, lightness, 0.55)
        colors.append(mcolors.to_hex((r, g, b)))
    return colors


def _text_color_for_bg(hex_color: str) -> str:
    """Pick readable text color (dark or light) for a given background hex color."""
    r, g, b = mcolors.to_rgb(hex_color)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return '#14100f' if luminance > 0.6 else '#fbf3f1'


def build_person_stage_figure(user: str, pivot: pd.DataFrame, workstream_hues: dict) -> go.Figure:
    """
    Single interactive chart for one person:
      - x-axis: workstream
      - y-axis: hours
      - each bar is stacked by the stages worked on within that workstream;
        each workstream has its own base color (shared across all charts via
        workstream_hues) and its stages ramp light -> dark within that color
        (largest stage segment lightest / at the bottom, smallest darkest /
        on top)
      - a label inside each stage segment showing its hours
      - a label above each bar showing the workstream's total hours
      - title: "<user> — <actual>/<allotted> hours"
    """
    workstreams = list(pivot.index)
    totals = pivot.sum(axis=1)
    actual_hours = float(totals.sum())

    fig = go.Figure()

    for ws in workstreams:
        row = pivot.loc[ws]
        row = row[row > 0].sort_values(ascending=False)  # biggest chunk first -> bottom, lightest
        base_hue = workstream_hues.get(ws, 0.0)
        colors = stage_color_ramp(base_hue, len(row))
        for stage, color in zip(row.index, colors):
            value = row[stage]
            fig.add_trace(go.Bar(
                x=[ws],
                y=[value],
                marker_color=color,
                marker_line=dict(color='#0d1b26', width=0.5),
                textfont=dict(color=_text_color_for_bg(color), size=11),
                name=stage,
                hovertemplate=f"<b>{ws}</b><br>{stage}: {value:.1f} hrs<extra></extra>",
                showlegend=False,
            ))

    # total label above each bar
    fig.add_trace(go.Scatter(
        x=workstreams,
        y=totals,
        mode='text',
        text=[f"{t:.1f}" for t in totals],
        textposition='top center',
        textfont=dict(color='#e8eef4', size=12, family='DejaVu Sans'),
        showlegend=False,
        hoverinfo='skip',
    ))

    max_val = max(totals.max(), 1) if len(totals) else 1

    fig.update_layout(
        barmode='stack',
        title=dict(
            text=f"{user} :  {actual_hours:.1f}/{ALLOTTED_HOURS_PER_WEEK} hours",
            font=dict(color='#e8eef4', size=16),
        ),
        xaxis=dict(
            tickangle=90,
            color='#e8eef4',
            gridcolor='#1a2a3a',
            automargin=True,
            categoryorder='array',
            categoryarray=workstreams,
        ),
        yaxis=dict(
            title='Hours',
            color='#e8eef4',
            gridcolor='#1a2a3a',
            rangemode='tozero',
            range=[0, max_val * 1.2],
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=60, b=110, l=50, r=20),
        height=430,
        bargap=0.35,
    )
    return fig


# --------------------------------------------------
#                       PAGE
# --------------------------------------------------


st.markdown("""
    <style>
    div.st-key-weekly_view_card {
        background-color: #ffffff00 !important;
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


def page2():
    inject_css()

    with st.container(border=True, key = "weekly_view_card"):
        st.markdown('#### Weekly Snapshot')

        df = load_data()

        # Convert to datetime
        df['week_start'] = pd.to_datetime(df['week_start'])

        all_weeks = df['week_start'].dropna().unique()

        # Ascending order, purely to compute correct "Week N" numbering
        weeks_asc = sorted(all_weeks)

        # Descending order, for how the dropdown is displayed (latest first)
        weeks_desc = sorted(all_weeks, reverse=True)

        # Week number resets for each month, counting forward chronologically
        week_labels = {}
        month_week_counter = {}

        for w in weeks_asc:
            ts = pd.Timestamp(w)
            month_key = (ts.year, ts.month)

            month_week_counter[month_key] = month_week_counter.get(month_key, 0) + 1

            week_labels[w] = (
                f"Week {month_week_counter[month_key]}: "
                f"{ts.strftime('%d %b %Y')}"
            )

        label_to_week = {v: k for k, v in week_labels.items()}

        # Dropdown still shows latest week first, but labels are now chronological
        week_label_options = [week_labels[w] for w in weeks_desc]

        if not week_label_options:
            st.markdown('_No dated entries found._')
            return

        if ('selected_week_label' not in st.session_state
                or st.session_state.selected_week_label not in week_label_options):
            st.session_state.selected_week_label = week_label_options[0]

        st.selectbox('Select Week', options=week_label_options, key='selected_week_label')

    current_week = label_to_week[st.session_state.selected_week_label]
    week_df = df[df['week_start'] == current_week]

    with st.container(border=True, key="weekly_view_card_ws_hours"):
        st.markdown("#### Where the hours went this week")
        st.markdown("Hours logged this week, by workstream (top 8; everything else rolled up).")
        if week_df.empty or pd.to_numeric(week_df['time_spent'], errors='coerce').fillna(0).sum() == 0:
            st.markdown('_No hours logged this week yet._')
        else:
            st.plotly_chart(
                fig_workstream_hours(week_df),
                use_container_width=True,
                key=f"weekly_ws_hours_{current_week}",
            )

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

    # ── Rework flags (computed against the FULL history so we know whether
    #    a project has ever bounced back to an earlier stage, and whether
    #    that bounce-back happened during the selected week specifically).
    #    NOTE: keyed by (user, workstream, project) — NOT just
    #    (workstream, project) — otherwise one teammate ticking the rework
    #    box on their own entry would incorrectly flag every other
    #    teammate's rows for the same project too.
    #
    #    'is_rework' is a STRING column — '', 'GC - Triggered', or
    #    'EQ - Triggered' — never a bool. Every check below compares it
    #    explicitly rather than using it directly as a boolean mask. ──
    rework_flags_all = compute_rework_flags(df)[
        ['user_name', 'workstream_name', 'project_name', 'date', 'is_rework']
    ]

    this_week_mask = (
        rework_flags_all['is_rework'].isin(["GC - Triggered", "EQ - Triggered"])
        & rework_flags_all['date'].isin(week_df['date'])
    )
    ever_mask = rework_flags_all['is_rework'] != ''

    reworked_this_week_keys = set(
        zip(
            rework_flags_all.loc[this_week_mask, 'user_name'],
            rework_flags_all.loc[this_week_mask, 'workstream_name'],
            rework_flags_all.loc[this_week_mask, 'project_name'],
        )
    )
    ever_reworked_keys = set(
        zip(
            rework_flags_all.loc[ever_mask, 'user_name'],
            rework_flags_all.loc[ever_mask, 'workstream_name'],
            rework_flags_all.loc[ever_mask, 'project_name'],
        )
    )

    def rework_label(row):
        key = (row['user_name'], row['workstream_name'], row['project_name'])
        if key in reworked_this_week_keys:
            return '⚠️ This week'
        elif key in ever_reworked_keys:
            return '↩️ Previously'
        return '—'

    if not result.empty:
        result['Reworked?'] = result.apply(rework_label, axis=1)

    result = result.sort_values(['user_name', 'workstream_name', 'project_name'])
    result = result.rename(columns={
        'user_name': 'Team Member',
        'workstream_name': 'Workstream',
        'project_name': 'Project Name',
        'hours_this_week': 'Hours (this week)',
        'latest_stage': 'Last thing did',
        'latest_status': 'Current Status',
    })
    
    with st.expander('View Logs'):

        if result.empty:
            st.markdown('_No hours logged this week._')
        else:
            with st.container():
                st.dataframe(result, use_container_width=True, height=min(900, 60 + 35 * len(result)))
            
    with st.container(border=True, key="weekly_view_card4"):
        st.markdown("#### Individual Workstream Breakdown")

        user_pivots = get_user_stage_workstream_hours(week_df)

        if not user_pivots:
            st.markdown('_No hours logged this week._')
        else:
            workstream_hues = build_workstream_hue_map(user_pivots)
            users = sorted(user_pivots.keys())
            n_cols = 2
            for row_start in range(0, len(users), n_cols):
                row_users = users[row_start: row_start + n_cols]
                cols = st.columns(len(row_users))
                for col, user in zip(cols, row_users):
                    pivot = user_pivots[user]
                    if pivot.empty:
                        with col:
                            st.markdown(f'_{user}: no hours logged this week._')
                        continue
                    fig = build_person_stage_figure(user, pivot, workstream_hues)
                    col.plotly_chart(fig, use_container_width=True, key=f"user_chart_{user}_{current_week}")
    
    with st.expander('View Executive Project Summary'):
        with st.container(border=True, key = "weekly_view_card2"):
            st.markdown("#### Executive Project Summary")
            st.markdown('**Project Services Summary**')
            ops_summary = get_workstream_ops_summary(week_df)
            ops_summary = ops_summary.rename(columns={
                'workstream_name': 'Workstream',
                'total_touched': 'Projects Kicked-off',
                'completed_count': 'Projects Completed',
                'all_projects': 'All Projects',
                'in_progress_projects': 'In Progress Projects',
            })
            if ops_summary.empty:
                st.markdown('_No hours logged this week._')
            else:
                st.dataframe(ops_summary)
                
            st.markdown("**R&D Summary**")
            
            st.markdown('Quantitative')
            
            paddock_summary = get_paddock_als_cpc_summary(week_df)
            if paddock_summary.empty:
                    st.markdown('_No hours logged this week._')
            else:
                st.dataframe(paddock_summary)
            
            st.markdown('Qualitative')

            rnd_summary = get_workstream_rnd_summary(week_df)
            if rnd_summary.empty:
                st.markdown('_No hours logged this week._')
            else:
                st.dataframe(rnd_summary)
page2()