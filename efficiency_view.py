import pandas as pd
import streamlit as st

from pathlib import Path

from db import load_data

# --------------------------------------------------
#                  CONSTANTS
# --------------------------------------------------

TARGET_WORKSTREAM = 'miscellaneous'
TARGET_STAGES_TOOLS_AUTOMATION = {'tool building', 'automation'}
TARGET_STAGES_PROCESS_IMPROVEMENTS = {'process improvements'}


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
        </style>
    """, unsafe_allow_html=True)


# --------------------------------------------------
#                       PAGE
# --------------------------------------------------

def page5():
    inject_css()
    st.title('Improvements / Tool Usage')

    st.markdown('## Tool / Automation Usage')
    st.markdown(
        'Tools Build adding value in existing workstreams along with Manual v/s Automation/Tool Usage'
    )

    summary_tools_automation_df, summary_process_improvements_df = load_tool_usage_summary()

    # NOTE: kept identical to the original logic — if EITHER table is empty,
    # neither table is shown and only the message below is displayed.
    if summary_tools_automation_df.empty or summary_process_improvements_df.empty:
        st.markdown(
            '_No matching entries found. Check that stage values in the sheet match the expected labels._'
        )
        return

    st.dataframe(summary_tools_automation_df, use_container_width=True,
                 height=min(900, 60 + 35 * len(summary_tools_automation_df)))

    st.markdown('## Process Improvements')
    st.dataframe(summary_process_improvements_df, use_container_width=True,
                 height=min(900, 60 + 35 * len(summary_process_improvements_df)))


page5()