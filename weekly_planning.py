import streamlit as st
import pandas as pd
from datetime import date

from daily_entry import load_project_list
from db import append_entry_sheet2

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

project_names = load_project_list()

# --------------------------------------------------
#         SESSION STATE DEFAULTS
# --------------------------------------------------

if 'wp_week_start' not in st.session_state:
    st.session_state['wp_week_start'] = date.today()

if 'wp_workstream_name' not in st.session_state:
    st.session_state['wp_workstream_name'] = None

if 'wp_project_names' not in st.session_state:
    st.session_state['wp_project_names'] = []

if 'wp_visible_in_tracker' not in st.session_state:
    st.session_state['wp_visible_in_tracker'] = False

if 'wp_files_received' not in st.session_state:
    st.session_state['wp_files_received'] = False


# --------------------------------------------------
#                   SAVE / SUBMIT
# --------------------------------------------------

def submit_weekly_entry():
    week_start_val = st.session_state.wp_week_start
    week_str = week_start_val.isoformat() if hasattr(week_start_val, 'isoformat') else str(week_start_val)

    workstream = st.session_state.wp_workstream_name
    selected_projects = st.session_state.wp_project_names

    if not workstream or not selected_projects:
        st.session_state['_wp_error'] = "Please select a workstream and at least one project."
        return

    for project in selected_projects:
        row_data = {
            'sheet': 'Sheet2',  # tells Apps Script which tab to append to
            'week_start': week_str,
            'workstream_name': workstream,
            'project_name': project,
            'visible_in_tracker': st.session_state.wp_visible_in_tracker,
            'files_received': st.session_state.wp_files_received,
        }
        append_entry_sheet2(row_data)

    # Clear the form after a successful submit
    st.session_state.wp_workstream_name = None
    st.session_state.wp_project_names = []
    st.session_state.wp_visible_in_tracker = False
    st.session_state.wp_files_received = False
    st.session_state['_wp_just_submitted'] = True
    st.session_state.pop('_wp_error', None)


# --------------------------------------------------
#                       UI
# --------------------------------------------------

st.markdown('#### Weekly Planning Entry')

st.date_input(label="Select week", key='wp_week_start')

st.selectbox('Select Workstream', options=workstreams_list_delivery,
             index=None, placeholder='Select workstream', key='wp_workstream_name')

st.multiselect('Select Project', options=project_names, key='wp_project_names')

st.checkbox("Visible in the Master Tracker?", key='wp_visible_in_tracker')
st.checkbox("Files Received in the Drive?", key='wp_files_received')

st.button("Submit", type='primary', on_click=submit_weekly_entry, key='wp_submit_button')

if st.session_state.pop('_wp_just_submitted', False):
    st.success("Weekly entries submitted!")

if st.session_state.get('_wp_error'):
    st.error(st.session_state['_wp_error'])