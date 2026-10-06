"""
Home page: one-screen summary of what every other view knows.

Sections
  1. Headline (this week) + four project-status tiles, all time
                                              (Delivered, Project Journey, Rework)
  2. Who has / hasn't logged today            (Daily Log Entry)
  3. Hours per week (10-week trend)           (full breakdown -> Weekly Snapshot)
  4. What open projects are waiting on
  5. Needs attention: blocked, gone quiet, rework   (Project Journey / Delivered)
  6. Since inception summary                  (full chart -> Monthly Recap)   [admin only]
  7. Latest log entries
  8. Links to every other page, each with a live figure

Definitions used throughout (same as the existing views, so numbers agree):
  * Week        = Thursday to Wednesday (db.load_data)
  * Completed   = an entry with status "completed" in a stage other than
                  Peer Review (delivered_view / monthly_view)
  * Open        = project with no such completed entry
  * In flight   = open AND last touched within OPEN_WINDOW_DAYS, so projects
                  abandoned long ago don't inflate "blocked" / "waiting on"
"""
import html
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db import load_data, workstreams_list_delivery

# --------------------------------------------------
#                  SETTINGS
# --------------------------------------------------

ALLOTTED_HOURS_PER_WEEK = 40     # same capacity weekly_view uses
TREND_WEEKS = 10                 # weeks shown in the hours trend
TEAM_LOOKBACK_DAYS = 56          # who counts as "on the team"
OPEN_WINDOW_DAYS = 60            # open project touched within this = in flight
QUIET_DAYS = 10                  # in flight + no entry for this long = "gone quiet"
REWORK_LOOKBACK_DAYS = 30

# Lifetime / monthly / lean figures come from admin-only pages. Flip to True
# if you want everyone to see them on the home page.
SHOW_RESTRICTED_TO_EVERYONE = False

PEER_REVIEW = 'peer review'
INVALID_NAMES = {'', 'nan', 'none', 'null', 'nat'}

INK = '#e8eef4'
MUTED = '#9fb3c0'
GRID = 'rgba(255,255,255,0.09)'
TEAL = '#5eead4'
VIOLET = '#a78bfa'
SLATE = '#64748b'
AMBER = '#fbbe24'
ROSE = '#ff6373'
ORANGE = '#fb923c'

CATEGORY_COLORS = {'Delivery': TEAL, 'R&D': VIOLET, 'Enablement & other': SLATE}

WAITING_COLORS = {
    'Still Processing': AMBER,
    'Awaiting Response - GC': ROSE,
    'Final QA - GC': ORANGE,
    'Peer Review - EQ': TEAL,
}

# Some rows are stored as "WS1:Paddock" and others as "WS1: Paddock".
# Normalise both sides so they group together.
def _norm_ws(name: str) -> str:
    return re.sub(r':\s*', ': ', str(name))


DELIVERY = {_norm_ws(w) for w in workstreams_list_delivery}

admin_emails = set(st.secrets.get("admin_emails", []))

user_email = st.user.email if st.user.is_logged_in else None
is_admin = bool(user_email and user_email.lower() in {e.lower() for e in admin_emails})


# --------------------------------------------------
#                  DATA
# --------------------------------------------------

@st.cache_data(ttl=120, show_spinner='Fetching latest entries…')
def fetch_log():
    """Cached for 2 minutes so the home page doesn't hit Apps Script on every
    click. The Refresh button clears it."""
    df = load_data()
    stamp = pd.Timestamp.now(tz='Asia/Kolkata').strftime('%d %b, %H:%M')
    return df, stamp


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    d = raw.copy()

    text_cols = ['user_name', 'workstream_name', 'project_name', 'stage', 'current_status',
                 'next_steps', 'work_type', 'is_rework', 'efficiency_description']
    for col in text_cols:
        if col not in d.columns:
            d[col] = ''
        d[col] = d[col].fillna('').astype(str).str.strip()

    d['time_spent'] = (
        pd.to_numeric(d['time_spent'], errors='coerce').fillna(0.0)
        if 'time_spent' in d.columns else 0.0
    )

    d = d[d['date'].notna()].copy()
    d['date'] = pd.to_datetime(d['date']).dt.normalize()
    d = d[~d['user_name'].str.lower().isin(INVALID_NAMES)]
    d = d.reset_index(drop=True)          # keeps sheet order for "latest entry" tie-breaks

    d['workstream_name'] = d['workstream_name'].map(_norm_ws)
    d['status'] = d['current_status'].str.lower()
    d['week_start'] = d['date'] - pd.to_timedelta((d['date'].dt.weekday - 3) % 7, unit='D')

    in_delivery = d['workstream_name'].isin(DELIVERY)
    is_rnd = (
        (d['work_type'].str.lower() == 'r&d')
        | (d['workstream_name'].str.lower() == 'research and development')
    )
    d['category'] = 'Enablement & other'
    d.loc[in_delivery, 'category'] = 'Delivery'
    d.loc[is_rnd, 'category'] = 'R&D'

    d['is_project'] = in_delivery & ~d['project_name'].str.lower().isin(INVALID_NAMES)
    return d


def build_project_table(d: pd.DataFrame) -> pd.DataFrame:
    """One row per (workstream, project) with latest state, completion and hours."""
    keys = ['workstream_name', 'project_name']
    p = d[d['is_project']].sort_values('date', kind='stable')

    latest = (
        p.groupby(keys, sort=False).tail(1)
         [keys + ['date', 'status', 'stage', 'user_name', 'next_steps']]
         .rename(columns={'date': 'last_date', 'status': 'latest_status',
                          'stage': 'latest_stage', 'user_name': 'last_by'})
    )
    eligible = p[(p['stage'].str.lower() != PEER_REVIEW) & (p['status'] == 'completed')]
    done = (
        eligible.groupby(keys, sort=False).tail(1)[keys + ['date', 'user_name']]
                .rename(columns={'date': 'completed_date', 'user_name': 'completed_by'})
    )
    hours = p.groupby(keys, as_index=False)['time_spent'].sum().rename(columns={'time_spent': 'hours'})

    t = latest.merge(done, on=keys, how='left').merge(hours, on=keys, how='left')
    t['is_complete'] = t['completed_date'].notna()
    return t


# --------------------------------------------------
#                  SMALL HELPERS
# --------------------------------------------------

def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def in_range(frame: pd.DataFrame, col: str, start, end) -> pd.DataFrame:
    return frame[(frame[col] >= start) & (frame[col] <= end)]


def count_projects(frame: pd.DataFrame) -> int:
    proj = frame[frame['is_project']]
    return len(proj[['workstream_name', 'project_name']].drop_duplicates())


def is_awaiting_gc(next_steps: pd.Series) -> pd.Series:
    """True where the latest 'next step' is (case-insensitively) 'Awaiting Response - GC'."""
    return next_steps.fillna('').astype(str).str.strip().str.lower() == 'awaiting response - gc'


# --------------------------------------------------
#                  STYLING
# --------------------------------------------------

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&display=swap');

    .hm-date { color: #9fb3c0; font-size: 0.95rem; margin: 0 0 0.35rem; }
    .hm-headline {
        font-family: 'Bricolage Grotesque', 'Segoe UI', sans-serif;
        font-weight: 700; font-size: clamp(1.8rem, 3.4vw, 2.7rem);
        line-height: 1.08; letter-spacing: -0.02em; max-width: 30ch; margin: 0;
    }
    .hm-subline { color: #c9d6de; font-size: 1.1rem; margin: 0.6rem 0 0; }

    .hm-kpis {
        display: grid; grid-template-columns: repeat(var(--cols, 4), minmax(0, 1fr));
        border-top: 1px solid rgba(255,255,255,0.22);
        border-bottom: 1px solid rgba(255,255,255,0.12);
        margin: 1.5rem 0 0.7rem;
    }
    .hm-kpi { padding: 1rem 0.9rem 1rem 1.1rem; border-left: 1px solid rgba(255,255,255,0.12); }
    .hm-kpi:first-child { border-left: none; padding-left: 0; }
    .hm-kpi-label { font-size: 0.88rem; color: #b7c7d1; }
    .hm-kpi-value {
        font-family: 'Bricolage Grotesque', 'Segoe UI', sans-serif;
        font-size: 2.3rem; font-weight: 700; line-height: 1.15; margin: 0.1rem 0 0.15rem;
    }
    .hm-kpi-note { font-size: 0.8rem; color: #9fb3c0; min-height: 1.1em; }
    .hm-kpi-note.good { color: #5eead4; }
    .hm-kpi-note.bad  { color: #ff8a98; }
    @media (max-width: 1000px) {
        .hm-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .hm-kpi, .hm-kpi:first-child { border-left: none; padding-left: 0; border-top: 1px solid rgba(255,255,255,0.10); }
    }
    @media (max-width: 560px) { .hm-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

    .hm-today { font-size: 0.95rem; color: #c9d6de; margin: 0.2rem 0 0; }
    .hm-today b { color: #ffffff; }

    .hm-sec { margin: 2.4rem 0 0.5rem; }
    .hm-sec-title {
        font-family: 'Bricolage Grotesque', 'Segoe UI', sans-serif;
        font-size: 1.3rem; font-weight: 700; letter-spacing: -0.01em;
    }
    .hm-sec-sub { color: #9fb3c0; font-size: 0.9rem; margin-top: 0.1rem; }
    </style>
    """, unsafe_allow_html=True)


def section(title: str, sub: str = ''):
    sub_html = f'<div class="hm-sec-sub">{html.escape(sub)}</div>' if sub else ''
    st.markdown(
        f'<div class="hm-sec"><div class="hm-sec-title">{html.escape(title)}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def kpi_band(items):
    """items: (label, value, note, css_class)"""
    cells = ''.join(
        f'<div class="hm-kpi"><div class="hm-kpi-label">{html.escape(label)}</div>'
        f'<div class="hm-kpi-value">{html.escape(str(value))}</div>'
        f'<div class="hm-kpi-note {css}">{html.escape(note)}</div></div>'
        for label, value, note, css in items
    )
    st.markdown(f'<div class="hm-kpis" style="--cols:{len(items)}">{cells}</div>', unsafe_allow_html=True)


def style_fig(fig: go.Figure, height: int, **layout) -> go.Figure:
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=INK), height=height,
        margin=dict(l=8, r=8, t=28, b=8), **layout,
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, color=INK)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, color=INK)
    return fig


# `use_container_width` is deprecated in newer Streamlit in favour of
# width='stretch'. Try the new spelling first so this page works on both.
def show_fig(fig: go.Figure, key: str):
    try:
        st.plotly_chart(fig, width='stretch', key=key, config={'displayModeBar': False})
    except (TypeError, st.errors.StreamlitAPIException):
        st.plotly_chart(fig, use_container_width=True, key=key, config={'displayModeBar': False})


def show_df(frame: pd.DataFrame, height: int):
    try:
        st.dataframe(frame, hide_index=True, width='stretch', height=height)
    except (TypeError, st.errors.StreamlitAPIException):
        st.dataframe(frame, hide_index=True, use_container_width=True, height=height)


# --------------------------------------------------
#                  CHARTS
# --------------------------------------------------

def fig_weekly_trend(d: pd.DataFrame, cur_ws: pd.Timestamp) -> go.Figure:
    weeks = [cur_ws - pd.Timedelta(weeks=i) for i in range(TREND_WEEKS - 1, -1, -1)]
    sub = d[d['week_start'].isin(weeks)]
    cats = list(CATEGORY_COLORS)

    if sub.empty:
        piv = pd.DataFrame(0.0, index=weeks, columns=cats)
    else:
        piv = (sub.groupby(['week_start', 'category'])['time_spent'].sum()
                  .unstack(fill_value=0.0)
                  .reindex(index=weeks, columns=cats, fill_value=0.0))

    labels = [w.strftime('%d %b') for w in weeks]
    labels[-1] = 'This week'
    totals = piv.sum(axis=1)
    capacity = (sub.groupby('week_start')['user_name'].nunique()
                   .reindex(weeks, fill_value=0) * ALLOTTED_HOURS_PER_WEEK)

    fig = go.Figure()
    for cat in cats:
        fig.add_trace(go.Bar(
            x=labels, y=piv[cat], name=cat, marker_color=CATEGORY_COLORS[cat],
            hovertemplate=f'{cat}: %{{y:.1f}} h<extra></extra>',
        ))
    fig.add_trace(go.Scatter(
        x=labels, y=totals, mode='text', showlegend=False, hoverinfo='skip',
        text=[f'{v:.0f}' if v else '' for v in totals], textposition='top center',
        textfont=dict(color=INK, size=12),
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=capacity, mode='lines', name=f'Capacity ({ALLOTTED_HOURS_PER_WEEK} h per person logging)',
        line=dict(color=MUTED, dash='dot', width=2),
        hovertemplate='Capacity: %{y:.0f} h<extra></extra>',
    ))
    style_fig(
        fig, 340, barmode='stack', bargap=0.3,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, font=dict(color=INK)),
    )
    fig.update_xaxes(type='category', categoryorder='array', categoryarray=labels)
    fig.update_yaxes(title='Hours', range=[0, max(totals.max(), capacity.max(), 1) * 1.18])
    return fig


def fig_waiting_on(inflight: pd.DataFrame) -> go.Figure:
    steps = inflight['next_steps'].where(~inflight['next_steps'].str.lower().isin(INVALID_NAMES), 'Not stated')
    counts = steps.value_counts()
    fig = go.Figure(go.Bar(
        x=counts.values, y=list(counts.index), orientation='h',
        marker_color=[WAITING_COLORS.get(k, SLATE) for k in counts.index],
        text=list(counts.values), textposition='outside', cliponaxis=False,
        hovertemplate='<b>%{y}</b><br>%{x} projects<extra></extra>',
    ))
    style_fig(fig, max(220, 52 * len(counts) + 60), bargap=0.35)
    fig.update_yaxes(autorange='reversed', automargin=True)
    fig.update_xaxes(range=[0, counts.max() * 1.2], title='Open projects', dtick=1)
    return fig


# --------------------------------------------------
#                  TABLES
# --------------------------------------------------

def project_attention_table(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[['workstream_name', 'project_name', 'latest_stage', 'last_by', 'last_date', 'days_since']].copy()
    out['last_date'] = out['last_date'].dt.strftime('%d %b')
    out.columns = ['Workstream', 'Project', 'Stage', 'Last worked by', 'Last update', 'Days ago']
    return out


def show_table(frame: pd.DataFrame, empty_msg: str):
    if frame.empty:
        st.caption(empty_msg)
    else:
        show_df(frame, min(420, 60 + 35 * len(frame)))


# --------------------------------------------------
#                  PAGE
# --------------------------------------------------

def page_home():
    inject_css()

    # ── data ──
    try:
        raw, fetched_at = fetch_log()
    except Exception as exc:  # network / Apps Script hiccup
        st.error(f"Couldn't load the log from Google Sheets: {exc}")
        if st.button('Try again'):
            st.rerun()
        return

    if raw.empty:
        st.info('Nothing has been logged yet. Add the first entry from Daily Log Entry.')
        st.page_link('daily_entry.py', label='Daily Log Entry', icon='📝')
        return

    d = prepare(raw)
    if d.empty:
        st.info('No dated entries found in the log yet.')
        return

    show_restricted = is_admin or SHOW_RESTRICTED_TO_EVERYONE

    today = pd.Timestamp.now(tz='Asia/Kolkata').tz_localize(None).normalize()
    cur_ws = today - pd.Timedelta(days=(today.weekday() - 3) % 7)
    cur_we = cur_ws + pd.Timedelta(days=6)

    t = build_project_table(d)
    t['days_since'] = (today - t['last_date']).dt.days
    open_projects = t[~t['is_complete']]
    inflight = open_projects[open_projects['days_since'] <= OPEN_WINDOW_DAYS]

    this_week = in_range(d, 'date', cur_ws, cur_we)

    team = sorted(
        set(d.loc[d['date'] >= today - pd.Timedelta(days=TEAM_LOOKBACK_DAYS), 'user_name'])
        | set(this_week['user_name'])
    )

    # ── this week (used by the headline) ──
    hours_now = float(this_week['time_spent'].sum())
    projects_now = count_projects(this_week)
    completed_now = len(in_range(t, 'completed_date', cur_ws, cur_we))
    rework_now = int((this_week['is_rework'] != '').sum())

    # ── all-time project status (used by the tiles) ──
    completed_total = int(t['is_complete'].sum())
    # "Blocked / awaiting GC response" counts projects whose latest status is
    # Blocked OR whose latest next step is "Awaiting Response - GC".
    is_blocked = (inflight['latest_status'] == 'blocked') | is_awaiting_gc(inflight['next_steps'])
    blocked = inflight[is_blocked]
    in_progress = inflight[~is_blocked]   # open and not blocked / awaiting GC
    stale_open = len(open_projects) - len(inflight)

    rework_rows = d[(d['is_rework'] != '') & d['workstream_name'].isin(DELIVERY)]
    rework_times = len(rework_rows)
    rework_projects = count_projects(rework_rows)

    # ── header ──
    head_col, refresh_col = st.columns([6, 1])
    with head_col:
        st.markdown(
            f'<div class="hm-date">{today.strftime("%A, %d %B %Y")}. '
            f'This week runs {cur_ws.strftime("%d %b")} to {cur_we.strftime("%d %b")}.</div>',
            unsafe_allow_html=True,
        )
        if hours_now > 0 and projects_now:
            headline = f'{hours_now:,.0f} hours logged this week across {plural(projects_now, "project")}'
        elif hours_now > 0:
            headline = f'{hours_now:,.0f} hours logged this week'
        else:
            headline = 'Nothing logged yet this week'
        # st.markdown(f'<h1 class="hm-headline">{html.escape(headline)}</h1>', unsafe_allow_html=True)

        parts = []
        if completed_now:
            parts.append(f'{completed_now} completed')
        if len(blocked):
            parts.append(f'{len(blocked)} blocked right now')
        if rework_now:
            parts.append(f'{rework_now} sent back for rework')
        subline = (', '.join(parts) + '.') if parts else 'No completions, blockers or rework so far.'
        # st.markdown(f'<p class="hm-subline">{html.escape(subline)}</p>', unsafe_allow_html=True)
    # with refresh_col:
    #     if st.button('Refresh data', key='home_refresh'):
    #         fetch_log.clear()
    #         st.rerun()
    #     st.caption(f'Pulled {fetched_at} IST')

    # ── status tiles (all time) ──
    kpi_band([
        ('Projects completed to date', completed_total,
         f'across {t.loc[t["is_complete"], "workstream_name"].nunique()} workstreams', 'good' if completed_total else ''),
        ('Projects in progress', len(in_progress),
         f'open, not blocked. {plural(stale_open, "older project")} untouched {OPEN_WINDOW_DAYS}+ days not counted'
         if stale_open else 'open, not blocked', ''),
        ('Awaiting GC response', len(blocked), f'of {len(inflight)} open projects', 'bad' if len(blocked) else ''),
        ('Times sent back for rework', rework_times, f'across {plural(rework_projects, "project")}',
         'bad' if rework_times else ''),
    ])

    # ── who has logged today (weekdays only) ──
    if today.weekday() < 5 and team:
        logged = sorted(set(d.loc[d['date'] == today, 'user_name']))
        pending = [u for u in team if u not in logged]
        if not pending:
            msg = '<b>Everyone has logged today.</b>'
        elif not logged:
            msg = f'Nobody has logged today yet: {html.escape(", ".join(pending))}.'
        else:
            msg = (f'Logged today: <b>{html.escape(", ".join(logged))}</b>. '
                   f'Still to log: {html.escape(", ".join(pending))}.')
        # st.markdown(f'<div class="hm-today">{msg}</div>', unsafe_allow_html=True)

    # ── hours ──
    section('Hours per week',
        f'Last {TREND_WEEKS} weeks, split by kind of work. The dotted line is {ALLOTTED_HOURS_PER_WEEK} h for everyone who logged that week.')
    show_fig(fig_weekly_trend(d, cur_ws), 'home_trend')
    
    section('What open projects are waiting on',
            f'Latest "next step" on each open project kicked-off in the last {OPEN_WINDOW_DAYS} days. '
            f'For hours per workstream this week, see Weekly Snapshot.')
    if inflight.empty:
        st.caption('No open projects in flight.')
    else:
        show_fig(fig_waiting_on(inflight), 'home_waiting')

    # ── needs attention ──
    quiet = inflight[(~is_blocked) & (inflight['days_since'] > QUIET_DAYS)]
    recent_rework = d[(d['is_rework'] != '') & (d['date'] >= today - pd.Timedelta(days=REWORK_LOOKBACK_DAYS))]

    section('Needs attention')
    tab_blocked, tab_rework = st.tabs([
        f'Blocked ({len(blocked)})',
        # f'Gone quiet ({len(quiet)})',
        f'Rework - last {REWORK_LOOKBACK_DAYS} days ({len(recent_rework)})',
    ])
    with tab_blocked:
        show_table(project_attention_table(blocked.sort_values('days_since', ascending=False)),
                   'Nothing is blocked. 🎉')
    # with tab_quiet:
    #     st.caption(f'Open, not blocked, and no entry for more than {QUIET_DAYS} days.')
    #     show_table(project_attention_table(quiet.sort_values('days_since', ascending=False)),
    #                'Every open project has been touched recently.')
    with tab_rework:
        rw = recent_rework.sort_values('date', ascending=False)[
            ['date', 'user_name', 'workstream_name', 'project_name', 'stage', 'is_rework']
        ].copy()
        rw['date'] = rw['date'].dt.strftime('%d %b')
        rw.columns = ['Date', 'Team member', 'Workstream', 'Project', 'Stage', 'Triggered by']
        show_table(rw, 'No rework flagged recently.')

    # ── since inception (admin) ──
    # section('Since inception')
    if not show_restricted:
        st.caption('Lifetime, monthly and lean-improvement figures are shown to admins. '
                   'Sign in from the sidebar to see them.')
    else:
        avg_hours = t.loc[t['is_complete'], 'hours'].mean() if completed_total else None

        ws_lower = d['workstream_name'].str.lower()
        stage_lower = d['stage'].str.lower()
        has_desc = ~d['efficiency_description'].str.lower().isin(INVALID_NAMES)
        pe = (ws_lower == 'productivity & enablement') & has_desc
        tools = d[pe & stage_lower.isin({'tool building', 'automation'})].groupby(
            ['user_name', 'efficiency_description']).ngroups
        process = d[pe & (stage_lower == 'process improvements')].groupby(
            ['user_name', 'efficiency_description']).ngroups

        rnd = d[d['category'] == 'R&D']

        # kpi_band([
        #     ('Average hours per delivery', f'{avg_hours:,.1f}' if avg_hours is not None else '–', 'logged on delivered projects', ''),
        #     ('Hours logged, all time', f'{d["time_spent"].sum():,.0f}', f'since {d["date"].min().strftime("%d %b %Y")}', ''),
        #     ('Lean improvements', tools + process, f'{tools} tools or automations, {process} process', ''),
        #     ('R&D entries', len(rnd), f'{rnd["time_spent"].sum():,.0f} h spent', ''),
        # ])

        month_start = today.replace(day=1)
        month_rows = d[(d['date'] >= month_start) & (d['category'] == 'Delivery')]
        done_month = t[t['completed_date'] >= month_start]
        top = done_month['completed_by'].value_counts()

        line = (f'{today.strftime("%B")}: {len(done_month)} completed, '
                f'{count_projects(month_rows)} projects touched, '
                f'{month_rows["time_spent"].sum():,.1f} delivery hours.')
        if len(top):
            line += f' Most completions: {top.index[0]} ({top.iloc[0]}).'
        # st.caption(line)
 

    # # ── links ──
    # section('Go to')
    # links = [
    #     ('daily_entry.py', 'Daily Log Entry', '📝', 'Log today’s work', False),
    #     ('weekly_view.py', 'Weekly Snapshot', '📅', f'{hours_now:,.0f} h logged this week', False),
    #     ('weekly_planning.py', 'Weekly Planning Entry', '🗓️', 'Mark projects visible or received', True),
    #     ('monthly_view.py', 'Monthly Recap', '📊', f'{len(t[t["completed_date"] >= today.replace(day=1)])} completed in {today.strftime("%B")}', True),
    #     ('delivered_view.py', 'Delivered - Since Inception', '✅', f'{int(t["is_complete"].sum())} projects delivered', True),
    #     ('efficiency_view.py', 'Lean Improvements', '⚡', 'Tools, automation and process fixes', True),
    #     ('project_journey_view.py', 'Project Journey', '🧭', f'{len(blocked)} blocked, {len(quiet)} gone quiet', True),
    #     ('rasci_view.py', 'RASCI Matrix', '🧩', 'Who owns each workstream', True),
    # ]
    # visible = [l for l in links if not l[4] or is_admin]
    # for start in range(0, len(visible), 4):
    #     cols = st.columns(4)
    #     for col, (path, label, icon, blurb, _) in zip(cols, visible[start:start + 4]):
    #         with col:
    #             st.page_link(path, label=label, icon=icon)
    #             st.caption(blurb)


page_home()