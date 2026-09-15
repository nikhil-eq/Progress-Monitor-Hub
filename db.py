import requests
import pandas as pd
from pathlib import Path

# ── Paste your Apps Script Web App URL here ──
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyoGne89Me-icxBtt-nmCMOYBKMwnd6I3roOc6tHVN0wuufVREFuR0Ra1dN9olmzvhAFQ/exec"

# Keep local reference for project names (this stays as Excel)
PROJECT_EXCEL = Path('Change Detection Tracker - Updated.xlsx')


workstreams_list_delivery = [
    'Initial Stratification - HIR',
    'Initial Stratification - NFMR',
    'Restratification - HIR',
    'Restratification - NFMR',
    'Restratification - Regen Check',
    'Restratification - AD',
    'Change Detection',
    'WS1:Paddock Mapping and Digitization',
    'WS3:ALS-to-CPC',
    'Fire Impact Assessment',
    'Grid Creation',
    'Spatial Data Cleaning and Ingestion',
    'AD Survey Packages',
    'Field Survey Packages',
    'Adhoc Analysis',
    'Carbon Plus',
]


def load_data() -> pd.DataFrame:
    """Fetch all rows from the Google Sheet via Apps Script."""
    resp = requests.get(APPS_SCRIPT_URL, timeout=30)
    resp.raise_for_status()
    records = resp.json()
    
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame(records)
    
    # ── same cleaning you already do ──
    df['date'] = pd.to_datetime(df.get('date'), errors='coerce')
    df['date'] = df['date'].dt.tz_convert('Asia/Kolkata').dt.normalize().dt.tz_localize(None)
    for col in ['current_status', 'stage', 'workstream_name', 'project_name', 'user_name']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # 'is_rework' is now a self-reported checkbox on the Daily Log page
    # (see daily_entry.py). Older rows logged before that checkbox existed
    # won't have the column/value at all — treat those as False rather than
    # guessing.
    if 'is_rework' in df.columns:
        df['is_rework'] = (
            df['is_rework'].astype(str).str.strip().str.lower()
            .isin({'true', '1', '1.0', 'yes', 'y'})
        )
    else:
        df['is_rework'] = False
    
    if 'date' in df.columns and not df['date'].isna().all():
        days_since_thursday = (df['date'].dt.weekday - 3) % 7
        df['week_start'] = df['date'] - pd.to_timedelta(days_since_thursday, unit='D')
        df['month_start'] = df['date'].dt.to_period('M').dt.to_timestamp()
    
    return df


def append_entry(row_dict: dict) -> dict:
    """Append one row to the Google Sheet via Apps Script."""
    # Clean values
    clean = {k: ("" if v is None else v) for k, v in row_dict.items()}
    resp = requests.post(APPS_SCRIPT_URL, json=clean, timeout=30)
    resp.raise_for_status()
    return resp.json()


def load_project_names() -> list:
    """Local Excel — project names don't need to be in the cloud."""
    if not PROJECT_EXCEL.exists():
        return []
    df = pd.read_excel(PROJECT_EXCEL)
    return list(df['Project name']) if 'Project name' in df.columns else []


# --------------------------------------------------
#              REWORK (shared)
# --------------------------------------------------
#
# "Rework" is self-reported: the team member ticks a checkbox on the Daily
# Log page ("This is rework") when logging an entry that revisits a stage
# already completed/passed. load_data() already normalizes that column to a
# real bool. These helpers just filter/summarize it — no inference here,
# on purpose, since the team knows better than any heuristic whether
# something is genuinely rework.

def compute_rework_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a copy of df restricted to rows with workstream/project/stage/
    date all present, carrying the self-reported 'is_rework' bool column
    (kept as a function, rather than inlining this everywhere, so the three
    pages that use it — weekly, delivered, project journey — all stay in
    sync if the definition of "rework" ever changes again).
    """
    required = ['workstream_name', 'project_name', 'stage', 'date']
    df = df[df['workstream_name'].isin(workstreams_list_delivery)].copy()
    d = df.dropna(subset=[c for c in required if c in df.columns]).copy()
    if 'is_rework' not in d.columns:
        d['is_rework'] = False
    d['is_rework'] = d['is_rework'].fillna(False).astype(bool)
    return d


def get_rework_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (workstream, project) that has ever been flagged as rework,
    with the stage(s) involved, how many times, and the most recent
    rework date — handy for a "flag these for follow-up" table.
    """
    flagged = compute_rework_flags(df)
    reworked = flagged[flagged['is_rework']]

    cols = ['workstream_name', 'project_name', 'reworked_stages', 'rework_count', 'last_rework_date']
    if reworked.empty:
        return pd.DataFrame(columns=cols)

    summary = (
        reworked.groupby(['workstream_name', 'project_name'])
                .agg(
                    reworked_stages=('stage', lambda s: ', '.join(sorted(set(s)))),
                    rework_count=('stage', 'count'),
                    last_rework_date=('date', 'max'),
                )
                .reset_index()
    )
    return summary[cols]