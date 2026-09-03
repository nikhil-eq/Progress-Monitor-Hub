import requests
import pandas as pd
from pathlib import Path

# ── Paste your Apps Script Web App URL here ──
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyoGne89Me-icxBtt-nmCMOYBKMwnd6I3roOc6tHVN0wuufVREFuR0Ra1dN9olmzvhAFQ/exec"

# Keep local reference for project names (this stays as Excel)
PROJECT_EXCEL = Path('Change Detection Tracker - Updated.xlsx')


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