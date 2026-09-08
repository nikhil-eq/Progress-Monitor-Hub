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

    # ── Timeline chart ──
    st.markdown("### Project Timeline")

    status_colors = {
        'in progress': '#fbbf24',
        'completed': '#34d399',
        'blocked': '#fb7185',
    }
    colors = journey['current_status'].str.lower().map(status_colors).fillna('#8fa3b8')

    # marker size scaled by hours spent (with a floor so small entries stay visible)
    sizes = (journey['time_spent'].fillna(0) * 40).clip(lower=60, upper=600)

    fig, ax = plt.subplots(figsize=(10, max(3, 0.5 * journey['stage'].nunique() + 1)))
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)

    ax.plot(journey['date'], journey['stage'], color='#3a4a5a', linewidth=1.5, zorder=1)
    ax.scatter(journey['date'], journey['stage'], s=sizes, c=colors, zorder=2, edgecolors='#0a1628')

    for _, row in journey.iterrows():
        ax.annotate(
            f"{row['time_spent']:.1f}h",
            (row['date'], row['stage']),
            textcoords="offset points", xytext=(0, 10),
            ha='center', fontsize=8, color='#e8eef4',
        )

    text_color = "#e8eef4"
    ax.set_xlabel('Date', color=text_color)
    ax.set_ylabel('Stage', color=text_color)
    ax.tick_params(colors=text_color)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    for spine in ax.spines.values():
        spine.set_color("#3a4a5a")
    fig.autofmt_xdate()
    fig.tight_layout()

    st.pyplot(fig)

    # legend key (matplotlib legend with scatter dots is fiddly with categorical y-axis,
    # so a simple markdown key is more reliable here)
    st.markdown(
        "🟡 In Progress &nbsp;&nbsp; 🟢 Completed &nbsp;&nbsp; 🔴 Blocked &nbsp;&nbsp; "
        "(marker size = hours spent that day)"
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