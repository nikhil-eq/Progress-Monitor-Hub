import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from db import load_data, compute_rework_flags

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

    # Flag any entry that returns to a stage the team had already moved
    # past (e.g. Peer Review -> back to Processing) as "rework", BEFORE
    # the stage column is turned into a Categorical below. Assign by the
    # original row index (NOT a date+stage merge) — merging on date+stage
    # would duplicate rows whenever two people log the same stage on the
    # same day.
    #
    # 'is_rework' is a STRING column — '', 'GC - Triggered', or
    # 'EQ - Triggered' — never a bool. It's kept as the string here (so the
    # detail table below can show which side triggered it), and converted
    # to an actual boolean explicitly wherever yes/no logic is needed.
    flagged = compute_rework_flags(journey)
    journey['is_rework'] = flagged['is_rework'].fillna('')

    # order stages by the order they first appear, so the y-axis reads
    # as a logical process sequence rather than alphabetically
    stage_order = list(dict.fromkeys(journey['stage']))
    journey['stage'] = pd.Categorical(journey['stage'], categories=stage_order, ordered=True)

    return journey


# --------------------------------------------------
#                   CHART BUILDER
# --------------------------------------------------

def build_journey_timeline_figure(daily: pd.DataFrame, status_colors: dict, blocked_color: str) -> go.Figure:
    """
    Interactive Plotly version of the project timeline: one bar per
    (day, stage) entry, stacked by day, colored by that entry's status.
    Gaps between active days are shaded as "blocked" periods, and rework
    entries (bounced back to an earlier stage) get a hatched pattern and a
    red outline. Hover any segment for the exact date, stage, status and
    hours.

    'daily' carries an 'is_rework' column that is already a plain bool
    (aggregated with .any() in page_project_journey below), so it's safe
    to use directly here with bool(...).
    """
    daily = daily.sort_values('date').reset_index(drop=True)

    active_dates = sorted(daily['date'].drop_duplicates().tolist())
    span_days = max((active_dates[-1] - active_dates[0]).days, 1)
    bar_width_days = max(span_days * 0.012, 1)
    half_width = pd.Timedelta(days=bar_width_days / 2)
    width_ms = bar_width_days * 24 * 60 * 60 * 1000

    all_days = pd.date_range(active_dates[0], active_dates[-1], freq='D')
    active_set = set(active_dates)

    inactive_days = [
        d for d in all_days
        if d not in active_set and d.weekday() < 5
    ]

    gap_spans = []
    for d in inactive_days:
        if gap_spans and (d - gap_spans[-1][1]).days == 1:
            gap_spans[-1] = (gap_spans[-1][0], d)
        else:
            gap_spans.append((d, d))

    # full height for the gap shading, with a little headroom
    y_top = daily.groupby('date')['hours'].sum().max() * 1.08

    fig = go.Figure()

    day_half = pd.Timedelta(hours=12)   # a bar is centred on midnight, so ±12h = exactly one day cell

    for start, end in gap_spans:
        x0 = start - day_half
        x1 = end + day_half
        fig.add_trace(go.Bar(
            x=[x0 + (x1 - x0) / 2],
            y=[y_top], base=[0],
            width=(x1 - x0).total_seconds() * 1000,
            marker=dict(color=blocked_color, line=dict(width=0)),
            showlegend=False,
            hovertemplate=(
                f"<b>🔴 Awaiting GC Response</b><br>"
                f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}<br>"
                f"With GC on decision points"
                + "<extra></extra>"
            ),
        ))

    bottoms = {}
    for _, row in daily.iterrows():
        d = row['date']
        h = row['hours']
        if h <= 0:
            continue

        status = str(row['current_status']).strip().lower()
        color = status_colors.get(status, '#ff0000')
        bottom = bottoms.get(d, 0)
        is_rework_bar = bool(row['is_rework'])

        marker = dict(
            color=color,
            line=dict(
                color='#ff0033' if is_rework_bar else '#0a1628',
                width=2.2 if is_rework_bar else 0.6,
            ),
        )
        if is_rework_bar:
            marker['pattern'] = dict(
                shape='/', fillmode='overlay',
                bgcolor=color,            # the status color stays visible
                fgcolor='#ff0033', size=6, solidity=0.35,
            )

        fig.add_trace(go.Bar(
            x=[d], y=[h], base=[bottom],
            width=width_ms,
            marker=marker,
            text=[str(row['stage'])],
            textposition='inside',
            textangle=-90,
            insidetextanchor='middle',
            textfont=dict(color='#091A29', size=10),
            showlegend=False,
            hovertemplate=(
                f"<b>{d.strftime('%d %b %Y')}</b><br>"
                f"Stage: {row['stage']}<br>"
                f"Status: {row['current_status']}<br>"
                f"Hours: {h:.1f}"
                + ("<br>⚠️ Rework - returned to a previous stage" if is_rework_bar else "")
                + "<extra></extra>"
            ),
        ))
        bottoms[d] = bottom + h

    # legend proxies — each real bar above has its own trace with
    # showlegend=False, so add one dummy per status to drive the legend
    for status_label, color in status_colors.items():
        fig.add_trace(go.Bar(
            x=[], y=[], name=status_label.title(), marker_color=color, showlegend=True,
        ))

    text_color = '#e8eef4'
    fig.update_layout(
        title=dict(text='Project Timeline', font=dict(color=text_color, size=16)),
        xaxis=dict(title='Date', color=text_color, gridcolor='#1a2a3a', type='date', tickformat='%d %b', rangebreaks=[dict(bounds=['sat', 'mon'])]),
        yaxis=dict(title='Hours', color=text_color, gridcolor='#1a2a3a', range=[0, y_top]),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, font=dict(color=text_color)),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=480,
        margin=dict(l=10, r=10, t=70, b=40),
        bargap=0.15,
        barmode = 'overlay'
    )
    return fig


# --------------------------------------------------
#                       PAGE
# --------------------------------------------------

def page_project_journey():
    inject_css()
    st.markdown('#### Project Journey')

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
            font-size: 1.0rem !important;
            white-space: normal !important;
            overflow-wrap: break-word !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # 'is_rework' is a string ('', 'GC - Triggered', 'EQ - Triggered') —
    # filter with != '' rather than using the column as a boolean mask.
    rework_rows = journey[journey['is_rework'] != '']
    rework_count = len(rework_rows)
    reworked_stages = sorted(rework_rows['stage'].astype(str).unique())

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Days Active", total_days)
    col2.metric("Total Hours", f"{total_hours:,.1f}")
    col3.metric("Date Range", f"{start_date} - {end_date}")
    col4.metric("Latest Status", latest_status)
    col5.metric("Rework Events", rework_count)

    if rework_count:
        st.warning(
            f"⚠️ This project bounced back to a previous stage {rework_count} time(s): "
            f"{', '.join(reworked_stages)}."
        )

    # ── Timeline chart (interactive Plotly stacked bar) ──
    st.markdown("### Project Timeline")

    status_colors = {
        'in progress': 'rgba(251, 190, 36, 1)',    # was #fbbe24ff
        'completed':   '#34d399',
        'blocked':     'rgba(255, 99, 115, 0.675)', # was #b30c25ac  (0xac/255 ≈ 0.675)
    }
    
    blocked_color = status_colors['blocked']

    daily = (
        journey.groupby(['date', 'stage', 'current_status'], as_index=False, observed=True)
               .agg(
                   hours=('time_spent', 'sum'),
                   # aggregate the string column down to a real bool per
                   # (date, stage, status) group — True if ANY entry that
                   # day was flagged rework, regardless of which side
                   # triggered it. This is what build_journey_timeline_figure
                   # expects for its hatching.
                   is_rework=('is_rework', lambda s: (s != '').any()),
               )
    )
    daily['date'] = pd.to_datetime(daily['date']).dt.normalize()
    daily = daily.sort_values('date')

    fig = build_journey_timeline_figure(daily, status_colors, blocked_color)
    st.plotly_chart(fig, use_container_width=True, key=f"journey_timeline_{workstream}_{project}")

    st.markdown(
    """
    <div style="font-size: 14px;">
        🟡 <b>In Progress</b>
        &nbsp;&nbsp;
        🟢 <b>Completed</b>
        &nbsp;&nbsp;
        🔴 <b>Awaiting GC Response</b>
        &nbsp;&nbsp;
        ⚠️ hatched / red-bordered = rework
        <br>
        <span style="font-size: 12px; color: #9aa0a6;">
            Bar height = hours logged that day ·
            Red shading = gaps with no activity ·
            Text on each bar = stage worked ·
            Hatched/red-bordered bars = the team returned to a stage it had already left ·
            Hover any bar for details
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

    # ── Detail table ──
    detail_cols = ['date', 'user_name', 'stage', 'current_status', 'time_spent',
                   'today_update', 'next_steps', 'is_rework']
    detail = journey[[c for c in detail_cols if c in journey.columns]].copy()
    detail['date'] = detail['date'].dt.strftime('%d %b %Y')
    # is_rework is the trigger string itself ('', 'GC - Triggered',
    # 'EQ - Triggered') — show it directly rather than mapping a bool.
    detail['is_rework'] = detail['is_rework'].apply(
        lambda v: f'⚠️ Rework ({v})' if v else ''
    )
    detail = detail.rename(columns={
        'date': 'Date', 'user_name': 'Team Member', 'stage': 'Stage',
        'current_status': 'Status', 'time_spent': 'Hours',
        'today_update': 'Task Nature', 'next_steps': 'Next Steps',
        'is_rework': 'Flag',
    })
    
    st.markdown("")

    with st.expander("View Entry Logs"):
        st.dataframe(detail, use_container_width=True, height=min(600, 60 + 35 * len(detail)))


page_project_journey()