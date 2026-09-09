import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from db import load_data

from auth import require_auth
require_auth()


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
        </style>
    """, unsafe_allow_html=True)


# --------------------------------------------------
#          DATA-SHAPING FUNCTION
# --------------------------------------------------

def get_project_journey(df: pd.DataFrame, workstream: str, project: str) -> pd.DataFrame:
    """
    All logged entries for one (workstream, project), sorted chronologically,
    with the stage's first-appearance order preserved for plotting.
    """
    journey = df[
        (df['workstream_name'] == workstream) & (df['project_name'] == project)
    ].copy()

    journey = journey.sort_values('date').reset_index(drop=True)

    # order stages by the order they first appear, so the y-axis reads
    # as a logical process sequence rather than alphabetically
    stage_order = list(dict.fromkeys(journey['stage']))
    journey['stage'] = pd.Categorical(journey['stage'], categories=stage_order, ordered=True)

    return journey


# --------------------------------------------------
#                       PAGE
# --------------------------------------------------

def page_project_journey():
    inject_css()
    st.title('Project Journey')

    df = load_data()

    # only workstreams that actually have real project names
    workstream_options = sorted(
        df.loc[df['project_name'].notna() & (df['project_name'].str.lower() != 'nan'), 'workstream_name']
          .dropna().unique()
    )

    st.selectbox('Workstream', options=workstream_options, index=None,
                 placeholder='Select workstream', key='journey_workstream')

    workstream = st.session_state.get('journey_workstream')

    if not workstream:
        st.markdown('_Select a workstream to continue._')
        return

    project_options = sorted(
        df[df['workstream_name'] == workstream]['project_name'].dropna().unique()
    )
    project_options = [p for p in project_options if p and p.lower() != 'nan']

    st.selectbox('Project Name', options=project_options, index=None,
                 placeholder='Select project', key='journey_project')

    project = st.session_state.get('journey_project')

    if not project:
        st.markdown('_Select a project to see its journey._')
        return

    journey = get_project_journey(df, workstream, project)

    if journey.empty:
        st.markdown('_No entries found for this project._')
        return

    # ── Summary stats ──
    total_hours = journey['time_spent'].sum()
    total_days = journey['date'].dt.date.nunique()
    start_date = journey['date'].min().strftime('%d %b')   # dropped year — shorter
    end_date = journey['date'].max().strftime('%d %b')
    latest_status = journey.sort_values('date').iloc[-1]['current_status']

    st.markdown("""
        <style>
        div[data-testid="stMetricValue"] {
            font-size: 1.4rem !important;
            white-space: normal !important;
            overflow-wrap: break-word !important;
        }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Days Active", total_days)
    col2.metric("Total Hours", f"{total_hours:,.1f}")
    col3.metric("Date Range", f"{start_date} - {end_date}")
    col4.metric("Latest Status", latest_status)

    # ── Timeline chart (stacked bar chart) ──
    st.markdown("### Project Timeline")

    status_colors = {
        'in progress': '#fbbf24',
        'completed': '#34d399',
        'blocked': "#b30c25ac",
    }
    blocked_color = status_colors['blocked']

    daily = (
        journey.groupby(['date', 'stage', 'current_status'], as_index=False, observed=True)
               .agg(hours=('time_spent', 'sum'))
    )
    daily['date'] = pd.to_datetime(daily['date']).dt.normalize()
    daily = daily.sort_values('date')

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)

    # ---- bar width scaled to the date span, so bars stay visible ----
    active_dates = sorted(daily['date'].drop_duplicates().tolist())
    span_days = max((active_dates[-1] - active_dates[0]).days, 1)
    bar_width_days = max(span_days * 0.012, 1)   # scales with span, floor of 1.5 days

    # ---- shade EVERY gap between active days as "blocked" ----
    all_days = pd.date_range(active_dates[0], active_dates[-1], freq='D')
    active_set = set(active_dates)
    inactive_days = [d for d in all_days if d not in active_set]

    gap_spans = []
    for d in inactive_days:
        if gap_spans and (d - gap_spans[-1][1]).days == 1:
            gap_spans[-1] = (gap_spans[-1][0], d)
        else:
            gap_spans.append((d, d))

    for start, end in gap_spans:
        ax.axvspan(
            start - pd.Timedelta(days=bar_width_days / 2),
            end + pd.Timedelta(days=bar_width_days / 2),
            color=blocked_color, alpha=1, zorder=0, linewidth=0,
        )

    # ---- stacked bars: one bar per active day, one segment per stage logged ----
    bottoms = {}
    for _, row in daily.iterrows():
        d = row['date']
        h = row['hours']
        status = str(row['current_status']).strip().lower()
        color = status_colors.get(status, "#ff0000")
        bottom = bottoms.get(d, 0)

        ax.bar(d, h, bottom=bottom, width=bar_width_days, color=color,
               edgecolor='#0a1628', linewidth=0.6, zorder=2)

        if h > 0:
            ax.text(
                d, bottom + h / 2, str(row['stage']),
                ha='center', va='center', fontsize=8, color='#0a1628',
                rotation=90, zorder=3,
            )
        bottoms[d] = bottom + h

    text_color = "#ffffff"
    ax.set_xlabel('Date', color=text_color)
    ax.set_ylabel('Hours', color=text_color)
    ax.tick_params(colors=text_color)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    for spine in ax.spines.values():
        spine.set_color("#3a4a5a")
    fig.autofmt_xdate()
    fig.tight_layout()

    st.pyplot(fig)

    st.markdown(
    """
    <div style="font-size: 14px;">
        🟡 <b>In Progress</b>
        &nbsp;&nbsp;
        🟢 <b>Completed</b>
        &nbsp;&nbsp;
        🔴 <b>Blocked</b>
        <br>
        <span style="font-size: 12px; color: #9aa0a6;">
            Bar height = hours logged that day ·
            Red shading = gaps with no activity ·
            Text on each bar = stage worked
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

    # ── Detail table ──
    st.markdown("### Entry Log")
    detail_cols = ['date', 'user_name', 'stage', 'current_status', 'time_spent',
                   'today_update', 'next_steps']
    detail = journey[[c for c in detail_cols if c in journey.columns]].copy()
    detail['date'] = detail['date'].dt.strftime('%d %b %Y')
    detail = detail.rename(columns={
        'date': 'Date', 'user_name': 'Team Member', 'stage': 'Stage',
        'current_status': 'Status', 'time_spent': 'Hours',
        'today_update': 'Task Nature', 'next_steps': 'Next Steps',
    })

    st.dataframe(detail, use_container_width=True, height=min(600, 60 + 35 * len(detail)))


page_project_journey()