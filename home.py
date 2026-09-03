import solara
import pandas as pd
from pathlib import Path
from datetime import date, datetime, timedelta

import solara.lab

refresh_trigger = solara.reactive(0)

COLORS = {
    "bg_deep": "#242930",
    "bg_card": "#111a25",
    "bg_card_hover": "#162233",
    "border": "#1a2a3a",
    "border_light": "#243447",
    "text_primary": "#e8eef4",
    "text_secondary": "#8fa3b8",
    "text_muted": "#5a6f85",
    "accent_cyan": "#22d3ee",
    "accent_green": "#34d399",
    "accent_amber": "#fbbf24",
    "accent_rose": "#fb7185",
    "accent_violet": "#a78bfa",
}

COLORS_NEW = {
    "bg_deep": "#7DB3BC",
    "bg_card": "#a3b5ac",
    "bg_card_hover": "#C5B7C5",
    "border": "#b5bcc2",
    "border_light": "#B0C5DF",
    "text_primary": "#000000",
    "text_secondary": "#464646",
    "text_muted": "#5a6f85",
    "accent_cyan": "#22d3ee",
    "accent_green": "#34d399",
    "accent_amber": "#fbbf24",
    "accent_rose": "#fb7185",
    "accent_violet": "#a78bfa",
}

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

NAV_CARDS = [
    {
        "title": "Daily Entry",
        "path": "/daily-entry",
        "desc": "Log your daily work, hours, and project updates.",
        "icon": "📝",
        "accent": COLORS["accent_cyan"],
    },
    {
        "title": "Weekly View",
        "path": "/weekly-view",
        "desc": "Review weekly hours, statuses, and last actions per project.",
        "icon": "📅",
        "accent": COLORS["accent_green"],
    },
    {
        "title": "Monthly View",
        "path": "/monthly-view",
        "desc": "Monthly project status snapshot and completion counts.",
        "icon": "📊",
        "accent": COLORS["accent_amber"],
    },
    {
        "title": "Lifetime View",
        "path": "/delivered-view",
        "desc": "Lifetime completed projects by workstream and month.",
        "icon": "✅",
        "accent": COLORS["accent_violet"],
    },
    {
        "title": "Efficiency View",
        "path": "/efficiency-view",
        "desc": "Tools, automation, and process improvements tracker.",
        "icon": "⚡",
        "accent": COLORS["accent_cyan"],
    },
    {
        "title": "R&D View",
        "path": "/rnd-view",
        "desc": "Research and development progress and trials log.",
        "icon": "🔬",
        "accent": COLORS["accent_rose"],
    },
]


# ── Data helpers ──
from db import load_data


def get_summary_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "total_hours_week": 0.0,
            "projects_completed": 0,
            "projects_in_progress": 0,
            'projects_blocked': 0,
            "active_team": 0,
            "tools_built": 0,
            "rnd_entries": 0,
        }

    this_week_start = pd.Timestamp(date.today() - timedelta(days=date.today().weekday()))
    week_df = df[df['week_start'] == this_week_start]

    # Completed projects (excluding peer review)
    eligible = df[df['stage'].str.lower() != 'peer review']
    completed_mask = eligible['current_status'].str.lower() == 'completed'
    completed_projects = eligible[completed_mask].groupby(['workstream_name', 'project_name']).ngroups

    # In progress
    in_progress_mask = df['current_status'].str.lower() == 'in progress'
    in_progress_projects = df[in_progress_mask].groupby(['workstream_name', 'project_name']).ngroups
    
    # blocked
    blocked_mask = df['current_status'].str.lower() == 'blocked'
    blocked_projects = df[blocked_mask].groupby(['workstream_name', 'project_name']).ngroups

    # Tools / Automation count
    tools_mask = (
        (df['workstream_name'].str.lower() == 'miscellaneous')
        & (df['stage'].str.lower().isin({'tool building', 'automation'}))
    )
    tools_built = df[tools_mask].groupby(['user_name', 'efficiency_description']).ngroups

    # R&D entries
    rnd_mask = df['workstream_name'].str.lower() == 'research and development'
    rnd_entries = df[rnd_mask].shape[0]

    return {
        "total_hours_week": round(week_df['time_spent'].sum(), 1),
        "projects_completed": completed_projects,
        "projects_in_progress": in_progress_projects,
        "projects_blocked": blocked_projects,
        "active_team": df['user_name'].nunique(),
        "tools_built": tools_built,
        "rnd_entries": rnd_entries,
    }


def get_recent_activity(df: pd.DataFrame, n: int = 7) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    recent = df.sort_values('date', ascending=False).head(n)
    return recent[['date', 'user_name', 'workstream_name', 'project_name', 'current_status', 'time_spent']].copy()


# ── Components ──
@solara.component
def StatCard(label: str, value: str, accent_color: str):
    with solara.Div(style={
        "background": COLORS["bg_card"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "12px",
        "padding": "20px",
        "minWidth": "160px",
        "flex": "1",
        "transition": "all 0.2s ease",
    }):
        solara.Div(style={
            "width": "4px",
            "height": "40px",
            "background": accent_color,
            "borderRadius": "2px",
            "marginBottom": "12px",
        })
        solara.Text(value, style={
            "fontSize": "32px",
            "fontWeight": "700",
            "color": COLORS["text_primary"],
            "fontFamily": "'Space Mono', monospace",
            "lineHeight": "1.2",
        })
        solara.Text(label, style={
            "fontSize": "13px",
            "color": COLORS["text_secondary"],
            "marginTop": "6px",
            "fontFamily": "'DM Sans', sans-serif",
            "letterSpacing": "0.3px",
        })


@solara.component
def NavCard(title: str, path: str, desc: str, icon: str, accent: str):
    router = solara.use_router()

    with solara.Div(style={
        "background": COLORS["bg_card"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "12px",
        "padding": "24px",
        "cursor": "pointer",
        "transition": "all 0.2s ease",
        "position": "relative",
        "overflow": "hidden",
    }, classes=["nav-card"], on_click=lambda: router.push(path)):
        # Accent top border
        solara.Div(style={
            "position": "absolute",
            "top": 0,
            "left": 0,
            "right": 0,
            "height": "3px",
            "background": accent,
            "borderRadius": "12px 12px 0 0",
        })
        solara.Div(style={"fontSize": "28px", "marginBottom": "12px"}, children=[icon])
        with solara.Column(style={
            "background": "radial-gradient(circle, rgba(34,211,238,0.08) 0%, transparent 70%)",
            "borderRadius": "50%",
            "pointerEvents": "none",
        }):
            solara.Text(title, style={
                "fontSize": "17px",
                "fontWeight": "600",
                "color": COLORS["text_primary"],
                "marginBottom": "6px",
                "fontFamily": "'DM Sans', sans-serif",
            })
            solara.Text(desc, style={
                "fontSize": "13px",
                "color": COLORS["text_secondary"],
                "lineHeight": "1.5",
                "fontFamily": "'DM Sans', sans-serif",
            })



@solara.component
def RecentActivityTable(df: pd.DataFrame):
    if df.empty:
        solara.Div(style={
            "textAlign": "center",
            "padding": "40px 20px",
            "color": COLORS["text_muted"],
        }, children=[
            "📭 No recent activity found. Start logging your work in Daily Entry!"
        ])
        return
    
    with solara.Div(style = {"background": "radial-gradient(circle, rgba(34,211,238,0.08) 0%, transparent 70%)",
            "borderRadius": "50%",
            "pointerEvents": "none"}):

        solara.Markdown("### Recent Activity", style = {"color": 'white'})
        display_df = df.copy()
        display_df['date'] = display_df['date'].dt.strftime('%d %b %Y')
        display_df = display_df.rename(columns={
            'date': 'Date',
            'user_name': 'Team Member',
            'workstream_name': 'Workstream',
            'project_name': 'Project',
            'current_status': 'Status',
            'time_spent': 'Hours',
        })
        solara.DataFrame(display_df)


@solara.component
def HeroSection():
    today = date.today().strftime("%A, %d %B %Y")
    with solara.Div(style={
        "background": f"linear-gradient(135deg, {COLORS['bg_deep']} 0%, #0d1a2a 60%, #081a10 100%)",
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "16px",
        "padding": "36px 32px",
        "marginBottom": "28px",
        "position": "relative",
        "overflow": "hidden",
    }): 
        # Decorative glow
        solara.Div(style={
            "position": "absolute",
            "top": "-60px",
            "right": "-60px",
            "width": "200px",
            "height": "200px",
            "background": "radial-gradient(circle, rgba(34,211,238,0.08) 0%, transparent 70%)",
            "borderRadius": "50%",
            "pointerEvents": "none",
        })
        with solara.Column(style={
            # "position": "absolute",
            # "top": "-60px",
            # "right": "-60px",
            # "width": "200px",
            # "height": "200px",
            "background": "radial-gradient(circle, rgba(34,211,238,0.08) 0%, transparent 70%)",
            "borderRadius": "50%",
            "pointerEvents": "none",
        }):
            solara.Text(
                "EQ < > GC Work Log",
                style={
                    "fontSize": "28px",
                    "fontWeight": "700",
                    "color": COLORS["text_primary"],
                    "fontFamily": "'Arial', sans-serif",
                    "letterSpacing": "-0.5px",
                },
            )

            solara.Text(
                f"{today}  ·  Geospatial Operations Dashboard",
                style={
                    "fontSize": "14px",
                    "color": COLORS["text_secondary"],
                    "fontFamily": "'DM Sans', sans-serif",
                    "marginTop": "4px",
                },
            )

@solara.component
def Page():

    # Force reactivity refresh
    _ = refresh_trigger.value
    df = load_data()
    stats = get_summary_stats(df)
    recent = get_recent_activity(df)

    solara.Title("EQ <> GC - Project Management and Planning")

    # Custom CSS for hover effects
    solara.HTML(tag="style", unsafe_innerHTML="""
    .nav-card:hover {
        background: #162233 !important;
        border-color: #2a3f55 !important;
        transform: translateY(-2px);
    }
    .nav-card:active {
        transform: translateY(0);
    }

    /* make the DataFrame table transparent / dark-theme friendly */
    .v-data-table,
    .v-data-table__wrapper,
    .v-table,
    .v-table__wrapper {
        background: transparent !important;
    }
    .v-data-table table,
    .v-data-table thead,
    .v-data-table tbody,
    .v-data-table tr {
        background: transparent !important;
    }
    .v-data-table th,
    .v-data-table td {
        background: transparent !important;
        color: #e8eef4 !important;
        border-bottom: 1px solid #1a2a3a !important;
        border-right: 1px solid #1a2a3a !important;
        padding: 0 16px !important;
    }
    .v-data-table th:last-child,
    .v-data-table td:last-child {
        border-right: none !important;
    }
    .v-data-table tbody tr:hover {
        background: #162233 !important;
    }
    .v-data-footer {
        background: transparent !important;
        color: #8fa3b8 !important;
    }
    """)

    HeroSection()

    # ── Stats Row ──
    with solara.Div(style={
        "display": "flex",
        "flexWrap": "wrap",
        "gap": "16px",
        "marginBottom": "28px",
    }):
        StatCard("  Hours this week", f"{stats['total_hours_week']}", COLORS["accent_cyan"])
        StatCard("  Projects completed", f"{stats['projects_completed']}", COLORS["accent_green"])
        StatCard("  In progress", f"{stats['projects_in_progress']}", COLORS["accent_amber"])
        StatCard("  Blocked", f"{stats['projects_blocked']}", COLORS["accent_rose"])
        StatCard("  Tools built", f"{stats['tools_built']}", COLORS["accent_cyan"])

    # ── Navigation Grid ──
    solara.Markdown("## Quick Navigation")
    with solara.Div(style={
        "display": "grid",
        "gridTemplateColumns": "repeat(auto-fit, minmax(260px, 1fr))",
        "gap": "16px",
        "marginBottom": "28px",
    }):
        for card in NAV_CARDS:
            NavCard(card["title"], card["path"], card["desc"], card["icon"], card["accent"])

    # ── Recent Activity ──
    with solara.Div(style={
        "background": COLORS["bg_card"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "12px",
        "padding": "24px",
    }):
        RecentActivityTable(recent)

    # ── Refresh button ──
    with solara.Div(style={"marginTop": "20px", "textAlign": "left"}):
        solara.Button(
            label="🔄 Refresh",
            on_click=lambda: refresh_trigger.set(refresh_trigger.value + 1),
            color="primary",
            text=True,
        )