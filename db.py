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

REWORK_TRIGGERS = {'GC - Oversight', 'EQ - Oversight'}


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


    if 'is_rework' in df.columns:
        df['is_rework'] = df['is_rework'].astype(str).str.strip()
        df['is_rework'] = df['is_rework'].where(df['is_rework'].isin(REWORK_TRIGGERS), '')
    else:
        df['is_rework'] = ''

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

def append_entry_sheet2(row_dict: dict) -> dict:
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

def compute_rework_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a copy of df restricted to rows with workstream/project/stage/
    date all present, carrying the self-reported 'is_rework' string column
    (kept as a function, rather than inlining this everywhere, so the pages
    that use it — weekly, delivered, project journey — all stay in sync if
    the definition of "rework" ever changes again).
    """
    required = ['workstream_name', 'project_name', 'stage', 'date']
    df = df[df['workstream_name'].isin(workstreams_list_delivery)].copy()
    d = df.dropna(subset=[c for c in required if c in df.columns]).copy()

    if 'is_rework' not in d.columns:
        d['is_rework'] = ''
    d['is_rework'] = d['is_rework'].fillna('').astype(str).str.strip()
    d['is_rework'] = d['is_rework'].where(d['is_rework'].isin(REWORK_TRIGGERS), '')
    return d


def get_rework_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (workstream, project) that has ever been flagged as rework,
    with the stage(s) involved, how many times, and the most recent
    rework date — handy for a "flag these for follow-up" table.
    """
    flagged = compute_rework_flags(df)
    reworked = flagged[flagged['is_rework'] != '']

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