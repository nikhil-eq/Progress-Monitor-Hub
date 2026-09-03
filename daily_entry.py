import pandas as pd
import streamlit as st

from pathlib import Path
from datetime import date

from db import append_entry, load_project_names

# --------------------------------------------------
#              DATABASE PATH
# --------------------------------------------------

EXCEL_PATH = Path('db.xlsx')

# --------------------------------------------------
#       WORKSTREAM NAMES and STAGES INVOLVED
# --------------------------------------------------

workstreams_list = [
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
    'Miscellaneous',
    'Research and Development',
    'Others (Neither Ops nor R&D)'
]

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


@st.cache_data
def load_project_list():
    xl_sheet = pd.read_excel('Change Detection Tracker - Updated.xlsx')
    return list(xl_sheet['Project name'])


project_names = load_project_list()

# --------------------------------------------------
#         SESSION STATE DEFAULTS (persist state
#         the same way solara.reactive did)
# --------------------------------------------------

TEXT_DEFAULTS = {
    'today_update': "",
    'next_steps': "",
    'broader_view': "",
    'efficiency_description': "",
    'rnd_explaination': "",
    'manual_against_automation': "",
}

SELECT_KEYS = [
    'workstream_name',
    'project_name',
    'stage',
    'current_status',
    'workstream_value_added',
]

if 'entry_date' not in st.session_state:
    st.session_state['entry_date'] = date.today()

if 'time_spent' not in st.session_state:
    st.session_state['time_spent'] = 0.0

for k, v in TEXT_DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

for k in SELECT_KEYS:
    if k not in st.session_state:
        st.session_state[k] = None

if 'user_name' not in st.session_state:
    st.session_state['user_name'] = None


# --------------------------------------------------
#                   SAVE / SUBMIT
# --------------------------------------------------

def save_name_to_excel(entry_date_val, name, workstream, project, status, stage_val,
                        today_update_val, steps, hours, broader_view_val,
                        efficiency_description_val, rnd_explaination_val,
                        workstream_value_added_val, manual_against_automation_val):
    if not name or not name.strip():
        return

    date_str = entry_date_val.isoformat() if hasattr(entry_date_val, 'isoformat') else str(entry_date_val)

    row_data = {
        'date': date_str,
        'user_name': name,
        'workstream_name': workstream,
        'project_name': project,
        'current_status': status,
        'stage': stage_val,
        'today_update': today_update_val,
        'next_steps': steps,
        'time_spent': hours,
        'broader_view': broader_view_val,
        'efficiency_description': efficiency_description_val,
        'rnd_explaination': rnd_explaination_val,
        'workstream_value_added': workstream_value_added_val,
        'manual_against_automation': manual_against_automation_val,
    }

    append_entry(row_data)


def submit_entry():
    save_name_to_excel(
        st.session_state.entry_date,
        st.session_state.user_name,
        st.session_state.workstream_name,
        st.session_state.project_name,
        st.session_state.current_status,
        st.session_state.stage,
        st.session_state.today_update,
        st.session_state.next_steps,
        st.session_state.time_spent,
        st.session_state.broader_view,
        st.session_state.efficiency_description,
        st.session_state.rnd_explaination,
        st.session_state.workstream_value_added,
        st.session_state.manual_against_automation,
    )

    # Clear the form after a successful submit, but keep the name.
    # This runs inside the on_click callback, i.e. before the widgets
    # are redrawn on the following rerun, so it is safe to mutate
    # session_state here.
    for k in SELECT_KEYS:
        st.session_state[k] = None
    for k in TEXT_DEFAULTS:
        st.session_state[k] = ""
    st.session_state.time_spent = 0.0

    st.session_state['_just_submitted'] = True


# --------------------------------------------------
#                       UI
# --------------------------------------------------

def team_info():
    st.selectbox(
        'Name',
        options=['Nikhil', 'Radha', 'Yogi', 'Rupaz'],
        index=None,
        placeholder='Select your name',
        key='user_name',
    )


def daily_entry_form():
    st.date_input('Select Date', key='entry_date')

    st.selectbox('Workstream', options=workstreams_list, index=None,
                 placeholder='Select workstream', key='workstream_name')

    workstream = st.session_state.workstream_name
    stage_val = st.session_state.stage

    if workstream not in ["Miscellaneous", "Carbon Plus", "Research and Development",
                          "Others (Neither Ops nor R&D)"]:
        st.selectbox('Project Name', options=project_names, index=None,
                     placeholder='Select project', key='project_name')

    if workstream in ['Initial Stratification - HIR']:
        st.selectbox('Stage', options=["Pre Processing", "Product Update", "Post Processing", "Peer Review"],
                     index=None, placeholder='Select stage', key='stage')

    elif workstream in ['Initial Stratification - NFMR']:
        st.selectbox('Stage', options=['Exclusions Delineation', 'CEAs Delineation', 'Peer Review'],
                     index=None, placeholder='Select stage', key='stage')

    elif workstream in ['Restratification - HIR', 'Restratification - NFMR', 'Restratification - Regen Check']:
        st.selectbox('Stage', options=["Iterative Failing Grid Removal", "0.2ha Compilance", "1.5km Radius Check",
                                       "Model Point Allocation", "Strata File Update",
                                       "Topology / Geometry Check", "Peer Review"],
                     index=None, placeholder='Select stage', key='stage')

    elif workstream in ['AD Survey Packages']:
        st.selectbox('Stage', options=["Track Digitisation", "Point / Plot Allocation", "Maps Preparation",
                                       "Peer Review"],
                     index=None, placeholder='Select stage', key='stage')

    elif workstream in ['Miscellaneous']:
        st.selectbox('Stage', options=["Meetings", "Process Improvements", "Tool Building",
                                       "Automation", "Debugging"],
                     index=None, placeholder='Select stage', key='stage')

    elif workstream in ['Research and Development']:
        st.selectbox('Stage', options=["iMAD", "WS3: ALS-to-CPC", "Fire Impact Assessment",
                                       "WS2: Allometric Equations"],
                     index=None, placeholder='Select stage', key='stage')

    elif workstream in ['Others (Neither Ops nor R&D)']:
        st.text_input('Work (e.g., Sheets / Tracker / 1:1 etc.,)', key='stage')

    elif workstream in workstreams_list:
        st.selectbox('Stage', options=['Processing', 'Peer Review'],
                     index=None, placeholder='Select stage', key='stage')

    # Re-read stage in case it was just set on this run
    stage_val = st.session_state.stage

    if (workstream in workstreams_list and workstream != 'Research and Development'
            and stage_val not in ["Process Improvements", "Tool Building", "Automation"]):
        st.text_input("Today's Update", key='today_update')

    if workstream != 'Others (Neither Ops nor R&D)':
        st.selectbox('Current Status', options=["In Progress", "Blocked", "Completed"],
                     index=None, placeholder='Select status', key='current_status')

    if stage_val in ['Process Improvements', 'Automation', 'Tool Building']:
        st.selectbox('Value Added Workstream?', options=workstreams_list_delivery,
                     index=None, placeholder='Select workstream', key='workstream_value_added')
        st.text_input('Broader View of Enhancements Made', key='broader_view')
        st.text_input('Detailed Description of Enhancement / Tool / Automation', key='efficiency_description')

    if stage_val in ['Automation', 'Tool Building']:
        st.text_input('Manual v/s Automated workflow gain', key='manual_against_automation')

    elif workstream in ['Research and Development']:
        st.text_input('In-detail Explaination of the progress / trials', key='rnd_explaination')

    st.text_input('Next Steps', key='next_steps')
    st.number_input('Time Spent (hours)', key='time_spent', step=0.5, format="%.2f")

st.markdown("""
    <style>
    div.st-key-daily_entry_card {
        background-color: #000000 !important;
        border-radius: 8px;
        padding: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

def page1():

    with st.container(border=True, key = "daily_entry_card"):

        st.markdown("### Daily Log Entry")
        st.markdown("Please Enter your Name to continue")

        team_info()

        if st.session_state.user_name not in [None, ""]:

            st.markdown(
                f"We Know You are Working Great, "
                f"{st.session_state.user_name}"
            )

            daily_entry_form()

            st.markdown("\n")
            st.markdown("\n")

            st.button(
                "Submit",
                on_click=submit_entry,
                type="primary", 
                key = "button"
            )

            if st.session_state.pop("_just_submitted", False):
                st.success("Entry submitted!")


page1()