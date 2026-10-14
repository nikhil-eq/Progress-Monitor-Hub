import html
import re
import textwrap

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pathlib import Path

from db import load_data

# --------------------------------------------------
#                  CONSTANTS
# --------------------------------------------------

TARGET_WORKSTREAM = 'productivity & enablement'
TARGET_STAGES_TOOLS_AUTOMATION = {'tool building', 'automation'}
TARGET_STAGES_PROCESS_IMPROVEMENTS = {'process improvements'}

INK = '#e8eef4'
MUTED = '#9fb3c0'
GRID = 'rgba(255,255,255,0.09)'
SURFACE = '#0e1117'

# One fixed color per kind of improvement (checked for color-blind separation
# on the dark background). R&D is violet, same as on the Home page.
KIND_COLORS = {
    'Tool Building': '#5eead4',
    'Automation': '#fbbe24',
    'Process Improvement': '#f472b6',
    'R&D': '#a78bfa',
}
KINDS = list(KIND_COLORS)
STAGE_TO_KIND = {
    'tool building': 'Tool Building',
    'automation': 'Automation',
    'process improvements': 'Process Improvement',
}
BLANKS = {'', 'nan', 'none', 'null'}


# --------------------------------------------------
#          DATA-SHAPING FUNCTION (unchanged)
# --------------------------------------------------

def load_tool_usage_summary() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = load_data()

    df['workstream_value_added'] = df['workstream_value_added'].astype(str).str.strip()
    df['broader_view'] = df['broader_view'].astype(str).str.strip()
    df['efficiency_description'] = df['efficiency_description'].astype(str).str.strip()
    df['manual_against_automation'] = df['manual_against_automation'].astype(str).str.strip()

    # For Tools and Automation Table

    mask_tools_automation = (
        (df['workstream_name'].str.lower() == TARGET_WORKSTREAM)
        & (df['stage'].str.lower().isin(TARGET_STAGES_TOOLS_AUTOMATION))
    )
    filtered_tools_automation = df[mask_tools_automation]

    summary_tools_automation = (
        filtered_tools_automation.groupby(
            ['user_name', 'workstream_value_added', 'broader_view',
             'efficiency_description', 'manual_against_automation'],
            as_index=False
        ).agg(hours_spent=('time_spent', 'sum'))
    )
    summary_tools_automation = summary_tools_automation.sort_values(
        ['user_name', 'workstream_value_added']
    ).reset_index(drop=True)

    # For Process Improvements Table

    mask_process_improvements = (
        (df['workstream_name'].str.lower() == TARGET_WORKSTREAM)
        & (df['stage'].str.lower().isin(TARGET_STAGES_PROCESS_IMPROVEMENTS))
    )

    filtered_process_improvements = df[mask_process_improvements]

    summary_process_improvements = (
        filtered_process_improvements.groupby(
            ['user_name', 'workstream_value_added', 'broader_view', 'efficiency_description'],
            as_index=False
        ).agg(hours_spent=('time_spent', 'sum'))
    )

    summary_process_improvements = summary_process_improvements.sort_values(
        ['user_name', 'workstream_value_added']
    ).reset_index(drop=True)

    return summary_tools_automation, summary_process_improvements

#----------------------------------------------------------
#                       Research and Development
#----------------------------------------------------------

# Separate name from TARGET_WORKSTREAM above — reusing that name here used to
# overwrite it, which emptied the Tools / Process Improvements tables.
RD_WORKSTREAM = 'research and development'


def load_rd_log() -> pd.DataFrame:
    """R&D entries: anything logged in the R&D workstream, plus R&D work
    logged under a delivery workstream (the Daily Log's R&D branch fills
    'rnd_explaination' and nothing else)."""
    df = load_data()

    explanation = df['rnd_explaination'].fillna('').astype(str).str.strip()
    mask = (
        (df['workstream_name'].str.lower() == RD_WORKSTREAM)
        | ~explanation.str.lower().isin(['', 'nan', 'none'])
    )
    rd_df = df[mask].copy()

    rd_df = rd_df.sort_values('date', ascending=False)
    rd_df['date'] = rd_df['date'].dt.strftime('%d %b %Y')
    return rd_df[['date', 'user_name', 'workstream_name', 'current_status', 'rnd_explaination', 'time_spent']]


# --------------------------------------------------
#          CHART DATA: every improvement, one row each
# --------------------------------------------------

def _clean(s: pd.Series) -> pd.Series:
    s = s.fillna('').astype(str).str.strip()
    return s.where(~s.str.lower().isin(BLANKS), '')


def load_improvements() -> pd.DataFrame:
    """
    One row per logged improvement — Tool Building / Automation / Process
    Improvement entries under Productivity & Enablement, plus R&D entries —
    with the workstream it helps, a short title and the full description.
    """
    df = load_data()
    for col in ['workstream_name', 'stage', 'user_name', 'workstream_value_added', 'broader_view',
                'efficiency_description', 'manual_against_automation', 'rnd_explaination',
                'current_status']:
        df[col] = _clean(df[col]) if col in df.columns else ''
    df['time_spent'] = pd.to_numeric(df['time_spent'], errors='coerce').fillna(0.0)
    df['workstream_name'] = df['workstream_name'].map(lambda w: re.sub(r':\s*', ': ', w))

    lean = df[(df['workstream_name'].str.lower() == TARGET_WORKSTREAM)
              & df['stage'].str.lower().isin(STAGE_TO_KIND)].copy()
    lean['kind'] = lean['stage'].str.lower().map(STAGE_TO_KIND)
    lean['helps'] = lean['workstream_value_added'].replace('', 'Not stated')
    lean['title'] = lean['broader_view'].where(lean['broader_view'] != '', lean['efficiency_description'])
    lean['detail'] = lean['efficiency_description']
    lean['gain'] = lean['manual_against_automation']

    rd = df[(df['workstream_name'].str.lower() == RD_WORKSTREAM) | (df['rnd_explaination'] != '')].copy()
    rd['kind'] = 'R&D'
    rd['helps'] = rd['workstream_name']
    rd['title'] = rd['rnd_explaination']
    rd['detail'] = ''
    rd['gain'] = ''

    cols = ['date', 'user_name', 'kind', 'helps', 'title', 'detail', 'gain', 'current_status', 'time_spent']
    out = pd.concat([lean[cols], rd[cols]], ignore_index=True)
    return out.sort_values('date').reset_index(drop=True)


def _wrap(text: str, width: int = 60) -> str:
    """Escape for Plotly hover HTML and break long text into lines."""
    return '<br>'.join(html.escape(line) for line in textwrap.wrap(text, width)) if text else ''


def _style(fig: go.Figure, height: int, **layout) -> go.Figure:
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=INK), height=height, margin=dict(l=8, r=8, t=36, b=8),
        hoverlabel=dict(bgcolor='#162233', bordercolor='#2a3f55', font=dict(color=INK, size=12)),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, font=dict(color=INK),
                    title_text='', traceorder='normal'),
        **layout,
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, color=MUTED, automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, color=INK, automargin=True)
    return fig


def fig_effort_by_workstream(imp: pd.DataFrame) -> go.Figure:
    """Stacked horizontal bars: hours put into improvements for each workstream
    they help, split by kind. Hover lists what was built."""
    totals = imp.groupby('helps')['time_spent'].sum().sort_values(ascending=False)
    order = list(totals.index)

    fig = go.Figure()
    for kind in KINDS:
        sub = imp[imp['kind'] == kind]
        if sub.empty:
            continue
        hours = sub.groupby('helps')['time_spent'].sum().reindex(order, fill_value=0.0)
        items = []
        for ws in order:
            titles = sub.loc[sub['helps'] == ws, 'title'].drop_duplicates()
            items.append('<br>'.join(f'• {_wrap(t, 55)}' for t in titles))
        fig.add_trace(go.Bar(
            y=order, x=hours.values, name=kind, orientation='h',
            marker=dict(color=KIND_COLORS[kind], line=dict(color=SURFACE, width=2)),
            customdata=items,
            hovertemplate=f'<b>%{{y}}</b> · {kind}<br>%{{x:.1f}} h<br><br>%{{customdata}}<extra></extra>',
        ))
    fig.add_trace(go.Scatter(
        y=order, x=totals.values, mode='text', showlegend=False, hoverinfo='skip',
        text=[f'{v:.1f} h' for v in totals.values], textposition='middle right',
        textfont=dict(color=INK, size=12),
    ))
    _style(fig, max(240, 46 * len(order) + 80), barmode='stack', bargap=0.35)
    fig.update_yaxes(autorange='reversed', automargin=True)
    fig.update_xaxes(title='Hours invested', range=[0, totals.max() * 1.25])
    return fig


def fig_timeline(imp: pd.DataFrame) -> go.Figure:
    """One dot per improvement over time, a lane per kind; dot size = hours.
    Hover shows who, what, and the manual-vs-automated gain."""
    kinds = [k for k in KINDS if k in set(imp['kind'])]
    max_h = max(imp['time_spent'].max(), 1.0)

    fig = go.Figure()
    for kind in kinds:
        sub = imp[imp['kind'] == kind]
        hover = []
        for _, r in sub.iterrows():
            parts = [f"<b>{_wrap(r['title'], 60)}</b>",
                     f"{r['date']:%d %b %Y} · {html.escape(r['user_name'])} · {r['time_spent']:.1f} h",
                     f"Helps: {html.escape(r['helps'])}"]
            if r['detail'] and r['detail'] != r['title']:
                parts.append(_wrap(r['detail'], 60))
            if r['gain']:
                parts.append(f"<i>Gain: {_wrap(r['gain'], 60)}</i>")
            if kind == 'R&D' and r['current_status']:
                parts.append(f"Status: {html.escape(r['current_status'])}")
            hover.append('<br>'.join(parts))
        fig.add_trace(go.Scatter(
            x=sub['date'], y=[kind] * len(sub), mode='markers', name=kind,
            marker=dict(color=KIND_COLORS[kind],
                        size=[10 + 26 * (h / max_h) ** 0.5 for h in sub['time_spent']],
                        line=dict(color=SURFACE, width=2), opacity=0.9),
            customdata=hover, hovertemplate='%{customdata}<extra></extra>',
        ))
    _style(fig, 90 * len(kinds) + 110, showlegend=False)
    fig.update_yaxes(categoryorder='array', categoryarray=kinds[::-1], automargin=True)
    fig.update_xaxes(title='', showgrid=True)
    return fig


def kpi_band(items):
    """items: (label, value, note)"""
    cells = ''.join(
        f'<div class="le-kpi"><div class="le-kpi-label">{html.escape(label)}</div>'
        f'<div class="le-kpi-value">{html.escape(str(value))}</div>'
        f'<div class="le-kpi-note">{html.escape(note)}</div></div>'
        for label, value, note in items
    )
    st.markdown(f'<div class="le-kpis" style="--cols:{len(items)}">{cells}</div>', unsafe_allow_html=True)


def show_fig(fig: go.Figure, key: str):
    try:
        st.plotly_chart(fig, width='stretch', key=key, config={'displayModeBar': False})
    except (TypeError, st.errors.StreamlitAPIException):
        st.plotly_chart(fig, use_container_width=True, key=key, config={'displayModeBar': False})


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

        .le-kpis {
            display: grid; grid-template-columns: repeat(var(--cols, 4), minmax(0, 1fr));
            border-top: 1px solid rgba(255,255,255,0.22);
            border-bottom: 1px solid rgba(255,255,255,0.12);
            margin: 0.8rem 0 1.2rem;
        }
        .le-kpi { padding: 0.9rem 0.9rem 0.9rem 1.1rem; border-left: 1px solid rgba(255,255,255,0.12); }
        .le-kpi:first-child { border-left: none; padding-left: 0; }
        .le-kpi-label { font-size: 0.88rem; color: #b7c7d1; }
        .le-kpi-value { font-size: 2.1rem; font-weight: 700; line-height: 1.15; margin: 0.1rem 0 0.15rem; }
        .le-kpi-note { font-size: 0.8rem; color: #9fb3c0; min-height: 1.1em; }
        @media (max-width: 1000px) {
            .le-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .le-kpi, .le-kpi:first-child { border-left: none; padding-left: 0; border-top: 1px solid rgba(255,255,255,0.10); }
        }
        </style>
    """, unsafe_allow_html=True)


# --------------------------------------------------
#                       PAGE
# --------------------------------------------------

def render_overview():
    """KPIs + interactive charts over every improvement, with filters on top."""
    imp = load_improvements()
    if imp.empty:
        st.markdown('_No improvements or R&D logged yet._')
        return

    f1, f2 = st.columns(2)
    with f1:
        people = st.multiselect('Team member', sorted(imp['user_name'].unique()),
                                placeholder='Everyone', key='lean_people')
    with f2:
        kinds = st.multiselect('Kind of improvement', [k for k in KINDS if k in set(imp['kind'])],
                               placeholder='All kinds', key='lean_kinds')
    if people:
        imp = imp[imp['user_name'].isin(people)]
    if kinds:
        imp = imp[imp['kind'].isin(kinds)]
    if imp.empty:
        st.markdown('_Nothing matches these filters._')
        return

    lean = imp[imp['kind'] != 'R&D']
    rd = imp[imp['kind'] == 'R&D']
    built = lean[lean['kind'].isin(['Tool Building', 'Automation'])]['title'].nunique()
    kpi_band([
        ('Hours on improvements', f"{imp['time_spent'].sum():,.1f}",
         f"{lean['time_spent'].sum():,.1f} h lean · {rd['time_spent'].sum():,.1f} h R&D"),
        ('Tools & automations', built, 'distinct tools / automations logged'),
        ('Workstreams helped', imp['helps'].nunique(), 'receiving tools, fixes or R&D'),
        ('Contributors', imp['user_name'].nunique(), ', '.join(sorted(imp['user_name'].unique()))),
    ])

    st.markdown('#### Where improvement effort went')
    st.markdown('Hours invested per workstream that benefits, split by kind. Hover a bar to see what was built.')
    show_fig(fig_effort_by_workstream(imp), 'lean_by_ws')

    st.markdown('#### Improvement timeline')
    st.markdown('Each dot is one logged entry; bigger dots took more hours. '
                'Hover for the details and the manual-vs-automated gain.')
    show_fig(fig_timeline(imp), 'lean_timeline')

    st.divider()


def page5():
    inject_css()
    st.markdown('### Lean Improvements')

    render_overview()

    summary_tools_automation_df, summary_process_improvements_df = load_tool_usage_summary()
    rd_df = load_rd_log()

    # Each table sits in its own dropdown (collapsed by default); an empty
    # table no longer hides the rest of the page.
    with st.expander(f'Tool / Automation Usage ({len(summary_tools_automation_df)})'):
        st.markdown(
            'Tools Build adding value in existing workstreams along with Manual v/s Automation/Tool Usage'
        )
        if summary_tools_automation_df.empty:
            st.markdown('_No Tool Building / Automation entries found._')
        else:
            st.dataframe(summary_tools_automation_df, use_container_width=True,
                         height=min(900, 60 + 35 * len(summary_tools_automation_df)))

    with st.expander(f'Process Improvements ({len(summary_process_improvements_df)})'):
        if summary_process_improvements_df.empty:
            st.markdown('_No Process Improvement entries found._')
        else:
            st.dataframe(summary_process_improvements_df, use_container_width=True,
                         height=min(900, 60 + 35 * len(summary_process_improvements_df)))

    with st.expander(f'Research and Development ({len(rd_df)})'):
        if rd_df.empty:
            st.markdown('_No Research and Development entries found._')
        else:
            result = rd_df.rename(columns={
                'date': 'Date',
                'user_name': 'Team Member',
                'workstream_name': 'Workstream',
                'current_status': 'Status',
                'rnd_explaination': 'Description',
                'time_spent': 'Time Spent (hrs)',
            })
            st.dataframe(result, use_container_width=True, height=min(900, 60 + 35 * len(result)))

page5()