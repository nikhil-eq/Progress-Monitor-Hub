import json
import pandas as pd
import streamlit as st

from pathlib import Path
from datetime import datetime

from db import load_data

# --------------------------------------------------
#                  CONSTANTS
# --------------------------------------------------

MATRIX_PATH = Path('rasci_matrix.json')

# Role codes. A trailing '*' means "tentative / target state" (the dashed
# circles in the original slide) — kept as a suffix rather than a separate
# column so one selectbox per cell covers both the role and its firmness.
ROLE_META = {
    'A':  ('Accountable', 'Owns the outcome',   '#c0272d', '#ffffff'),
    'R':  ('Responsible', 'Does the work',      '#2563eb', '#ffffff'),
    'S':  ('Support',     'Assists execution',  '#12a594', '#ffffff'),
    'C':  ('Consulted',   'Provides input',     '#f0ab00', '#3d2c00'),
    'I':  ('Informed',    'Kept in the loop',   '#8b9bb0', '#16202b'),
}

ROLE_OPTIONS = ['', 'A', 'R', 'S', 'C', 'I', 'A*', 'R*', 'S*', 'C*', 'I*']

LEVELS = ['Low', 'Medium', 'High']

VISIBILITY_COLORS = {'Low': '#cbe8c6', 'Medium': '#5aa84f', 'High': '#1d4620'}
DEPENDENCY_COLORS = {'Low': '#f6d2d2', 'Medium': '#e0656b', 'High': '#a3111f'}

DEFAULT_MEMBERS = ['Nikhil', 'Radha', 'Yoga', 'Rupaz', 'Subhadeep', 'Samreen']

DEFAULT_WORKSTREAMS = [
    'Restratification',
    'FIA',
    'Field Survey Packages',
    'Adhoc Analysis',
    'Initial Strat - HIR',
    'Initial Strat - NFMR',
    'WS1 - Paddock Mapping & Digitization',
    'WS3 - ALS to CPC',
    'AD Survey Packages',
    'Change Detection',
    'Workstream 2 - AD Enhancements',
]

# Seeded from the slide so the page is useful on first open.
DEFAULT_ASSIGNMENTS = {
    'Nikhil': {
        'Restratification': 'R*', 'FIA': 'R', 'Field Survey Packages': 'R*',
        'Adhoc Analysis': 'R', 'Initial Strat - HIR': 'R', 'Initial Strat - NFMR': 'R',
        'WS3 - ALS to CPC': 'R', 'AD Survey Packages': 'C', 'Change Detection': 'R',
    },
    'Radha': {
        'Restratification': 'C', 'Field Survey Packages': 'R', 'Adhoc Analysis': 'R',
        'Initial Strat - HIR': 'R*', 'Initial Strat - NFMR': 'R*',
    },
    'Yoga': {
        'Restratification': 'R', 'FIA': 'R*', 'Field Survey Packages': 'R*',
        'Initial Strat - HIR': 'R*', 'WS1 - Paddock Mapping & Digitization': 'R',
        'WS3 - ALS to CPC': 'R*', 'AD Survey Packages': 'R',
    },
    'Rupaz': {
        'Restratification': 'R*', 'Field Survey Packages': 'R*', 'Adhoc Analysis': 'S',
        'Initial Strat - HIR': 'R', 'Initial Strat - NFMR': 'R*',
        'WS1 - Paddock Mapping & Digitization': 'R', 'AD Survey Packages': 'R',
    },
    'Subhadeep': {
        'Restratification': 'C', 'FIA': 'C', 'Field Survey Packages': 'C',
        'Adhoc Analysis': 'C', 'Initial Strat - HIR': 'A', 'Initial Strat - NFMR': 'A',
        'WS1 - Paddock Mapping & Digitization': 'A', 'WS3 - ALS to CPC': 'A',
        'AD Survey Packages': 'C', 'Change Detection': 'C',
        'Workstream 2 - AD Enhancements': 'I',
    },
    'Samreen': {ws: 'I' for ws in DEFAULT_WORKSTREAMS},
}

DEFAULT_VISIBILITY = {
    'Restratification': 'Medium', 'FIA': 'Low', 'Field Survey Packages': 'Low',
    'Adhoc Analysis': 'Low', 'Initial Strat - HIR': 'Medium',
    'Initial Strat - NFMR': 'Medium', 'WS1 - Paddock Mapping & Digitization': 'High',
    'WS3 - ALS to CPC': 'Medium', 'AD Survey Packages': 'High',
    'Change Detection': 'Medium', 'Workstream 2 - AD Enhancements': 'Low',
}

DEFAULT_DEPENDENCY = {
    'Restratification': 'High', 'FIA': 'Low', 'Field Survey Packages': 'Low',
    'Adhoc Analysis': 'Low', 'Initial Strat - HIR': 'High',
    'Initial Strat - NFMR': 'High', 'WS1 - Paddock Mapping & Digitization': 'Medium',
    'WS3 - ALS to CPC': 'Medium', 'AD Survey Packages': 'Low',
    'Change Detection': 'Low', 'Workstream 2 - AD Enhancements': 'Low',
}


# --------------------------------------------------
#              LOAD / SAVE
# --------------------------------------------------

def default_matrix() -> dict:
    return {
        'members': list(DEFAULT_MEMBERS),
        'workstreams': list(DEFAULT_WORKSTREAMS),
        'assignments': {m: dict(DEFAULT_ASSIGNMENTS.get(m, {})) for m in DEFAULT_MEMBERS},
        'visibility': dict(DEFAULT_VISIBILITY),
        'dependency': dict(DEFAULT_DEPENDENCY),
        'updated_at': None,
        'updated_by': None,
    }


def load_matrix() -> dict:
    """Read the saved matrix, falling back to the seeded default.

    Note: this writes to the local filesystem. On Streamlit Community Cloud
    that disk is wiped on every redeploy/restart, so treat the JSON download
    below as the real backup — or point these two functions at the Apps
    Script sheet the way db.py does.
    """
    if not MATRIX_PATH.exists():
        return default_matrix()
    try:
        saved = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return default_matrix()

    base = default_matrix()
    base.update({k: v for k, v in saved.items() if k in base})
    return normalise_matrix(base)


def normalise_matrix(matrix: dict) -> dict:
    """Make sure every member has an entry for every workstream, and that
    no stale keys survive a rename or removal."""
    members = list(dict.fromkeys(matrix.get('members') or []))
    workstreams = list(dict.fromkeys(matrix.get('workstreams') or []))

    assignments = {}
    for m in members:
        row = (matrix.get('assignments') or {}).get(m, {})
        assignments[m] = {ws: row.get(ws, '') for ws in workstreams}

    matrix['members'] = members
    matrix['workstreams'] = workstreams
    matrix['assignments'] = assignments
    matrix['visibility'] = {ws: (matrix.get('visibility') or {}).get(ws, 'Low')
                            for ws in workstreams}
    matrix['dependency'] = {ws: (matrix.get('dependency') or {}).get(ws, 'Low')
                            for ws in workstreams}
    return matrix


def save_matrix(matrix: dict, who: str | None = None) -> None:
    matrix = normalise_matrix(matrix)
    matrix['updated_at'] = datetime.now().isoformat(timespec='seconds')
    matrix['updated_by'] = who
    MATRIX_PATH.write_text(json.dumps(matrix, indent=2), encoding='utf-8')


# --------------------------------------------------
#              SHAPE HELPERS
# --------------------------------------------------

def matrix_to_frame(matrix: dict) -> pd.DataFrame:
    rows = []
    for m in matrix['members']:
        row = {'Team member': m}
        row.update({ws: matrix['assignments'][m].get(ws, '') for ws in matrix['workstreams']})
        rows.append(row)
    return pd.DataFrame(rows, columns=['Team member'] + matrix['workstreams'])


def frame_to_assignments(edited: pd.DataFrame, workstreams: list) -> tuple[list, dict]:
    members, assignments = [], {}
    for _, row in edited.iterrows():
        name = str(row['Team member']).strip()
        if not name or name.lower() == 'nan':
            continue
        members.append(name)
        assignments[name] = {
            ws: str(row.get(ws, '') or '').strip().upper() for ws in workstreams
        }
    return members, assignments


def find_gaps(matrix: dict) -> tuple[list, list, list]:
    """Workstreams with no accountable owner, more than one, or nobody doing
    the work. A RASCI matrix that doesn't surface these isn't earning its keep."""
    no_owner, many_owners, no_doer = [], [], []
    for ws in matrix['workstreams']:
        codes = [matrix['assignments'][m].get(ws, '') for m in matrix['members']]
        firm = [c for c in codes if c and not c.endswith('*')]
        accountable = [c for c in firm if c == 'A']
        responsible = [c for c in codes if c.startswith('R')]
        if len(accountable) == 0:
            no_owner.append(ws)
        elif len(accountable) > 1:
            many_owners.append(ws)
        if not responsible:
            no_doer.append(ws)
    return no_owner, many_owners, no_doer


# --------------------------------------------------
#              RENDERING
# --------------------------------------------------

def inject_css():
    st.markdown("""
        <style>
        .rasci-wrap { overflow-x: auto; padding-bottom: 8px; }
        table.rasci {
            border-collapse: separate;
            border-spacing: 3px;
            width: 100%;
            min-width: 900px;
            color: #e8eef4;
        }
        table.rasci th.ws {
            background: rgba(255,255,255,0.04);
            border: 1px solid #2a3f55;
            border-radius: 6px;
            padding: 10px 8px 8px;
            font-size: 12px;
            font-weight: 600;
            line-height: 1.3;
            vertical-align: bottom;
            min-width: 108px;
            text-align: center;
        }
        table.rasci th.corner {
            background: transparent;
            text-align: left;
            font-size: 12px;
            color: #8fa3b8;
            font-style: italic;
            padding-left: 6px;
            vertical-align: bottom;
            min-width: 130px;
        }
        table.rasci td.member {
            background: rgba(255,255,255,0.04);
            border-radius: 6px;
            padding: 8px 12px;
            font-weight: 600;
            font-size: 14px;
            white-space: nowrap;
        }
        table.rasci td.cell {
            background: rgba(255,255,255,0.02);
            border-radius: 6px;
            text-align: center;
            padding: 6px;
            height: 48px;
        }
        .rasci-dot {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 34px; height: 34px;
            border-radius: 50%;
            font-weight: 700;
            font-size: 14px;
            font-family: 'DM Sans', sans-serif;
        }
        .rasci-dot.tentative {
            background: transparent !important;
            border: 2px dashed currentColor;
        }
        .ws-signal { display: flex; gap: 6px; justify-content: center; margin-top: 8px; }
        .ws-signal i {
            width: 11px; height: 11px; border-radius: 50%; display: inline-block;
        }
        .rasci-legend {
            display: flex; flex-wrap: wrap; gap: 20px 34px;
            align-items: center; font-size: 13px; margin-top: 4px;
        }
        .rasci-legend .item { display: flex; gap: 10px; align-items: center; }
        .rasci-legend .item small { color: #8fa3b8; display: block; font-size: 11px; }
        </style>
    """, unsafe_allow_html=True)


def dot_html(code: str) -> str:
    code = (code or '').strip().upper()
    if not code:
        return '&nbsp;'
    tentative = code.endswith('*')
    base = code.rstrip('*')
    if base not in ROLE_META:
        return '&nbsp;'
    _, _, bg, fg = ROLE_META[base]
    if tentative:
        return (f'<span class="rasci-dot tentative" style="color:{bg};" '
                f'title="Tentative / target state">{base}</span>')
    return f'<span class="rasci-dot" style="background:{bg};color:{fg};">{base}</span>'


def render_matrix_html(matrix: dict) -> str:
    head = ['<th class="corner">Team member</th>']
    for ws in matrix['workstreams']:
        vis = VISIBILITY_COLORS.get(matrix['visibility'].get(ws, 'Low'), '#cbe8c6')
        dep = DEPENDENCY_COLORS.get(matrix['dependency'].get(ws, 'Low'), '#f6d2d2')
        head.append(
            f'<th class="ws">{ws}'
            f'<div class="ws-signal">'
            f'<i style="background:{vis}" title="Visibility: {matrix["visibility"].get(ws)}"></i>'
            f'<i style="background:{dep}" title="Process dependency: {matrix["dependency"].get(ws)}"></i>'
            f'</div></th>'
        )

    body = []
    for m in matrix['members']:
        cells = [f'<td class="member">{m}</td>']
        for ws in matrix['workstreams']:
            cells.append(f'<td class="cell">{dot_html(matrix["assignments"][m].get(ws, ""))}</td>')
        body.append('<tr>' + ''.join(cells) + '</tr>')

    return (f'<div class="rasci-wrap"><table class="rasci">'
            f'<thead><tr>{"".join(head)}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def render_legend() -> str:
    items = []
    for code, (label, desc, bg, fg) in ROLE_META.items():
        items.append(
            f'<div class="item"><span class="rasci-dot" style="background:{bg};color:{fg};">'
            f'{code}</span><span><b>{label}</b><small>{desc}</small></span></div>'
        )
    items.append(
        '<div class="item"><span class="rasci-dot tentative" style="color:#8fa3b8;">R</span>'
        '<span><b>Tentative</b><small>Target state, add * to the code</small></span></div>'
    )
    return f'<div class="rasci-legend">{"".join(items)}</div>'


def signal_legend(title: str, colors: dict) -> str:
    dots = ''.join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:18px;">'
        f'<i style="width:11px;height:11px;border-radius:50%;background:{c};display:inline-block;"></i>'
        f'{lvl}</span>'
        for lvl, c in colors.items()
    )
    return (f'<div style="font-size:13px;margin-top:6px;">'
            f'<b style="margin-right:12px;">{title}</b>{dots}</div>')


# --------------------------------------------------
#                       PAGE
# --------------------------------------------------

def page_rasci():
    inject_css()
    st.markdown('#### RASCI Matrix')
    st.markdown(
        'Who owns, does, supports, advises and watches each workstream. '
        'Edit any cell below and save the change sticks for everyone.'
    )

    if 'rasci_matrix' not in st.session_state:
        st.session_state['rasci_matrix'] = load_matrix()

    matrix = normalise_matrix(st.session_state['rasci_matrix'])

    view_tab, edit_tab, setup_tab = st.tabs(['Matrix', 'Edit roles', 'Workstreams & people'])

    # ── Read-only view ──
    with view_tab:
        st.markdown(render_matrix_html(matrix), unsafe_allow_html=True)
        st.markdown('&nbsp;')
        st.markdown(render_legend(), unsafe_allow_html=True)
        st.markdown(signal_legend('Visibility', VISIBILITY_COLORS), unsafe_allow_html=True)
        st.markdown(signal_legend('Process dependency', DEPENDENCY_COLORS), unsafe_allow_html=True)

        no_owner, many_owners, no_doer = find_gaps(matrix)
        if no_owner:
            st.markdown('')
            st.warning(f"No accountable owner yet: {', '.join(no_owner)}.")
        if many_owners:
            st.warning(
                f"More than one person marked Accountable: {', '.join(many_owners)}. "
                "Accountability splits badly — pick one."
            )
        if no_doer:
            st.info(f"Nobody assigned to do the work: {', '.join(no_doer)}.")

        if matrix.get('updated_at'):
            stamp = datetime.fromisoformat(matrix['updated_at']).strftime('%d %b %Y, %H:%M')
            by = f" by {matrix['updated_by']}" if matrix.get('updated_by') else ''
            st.caption(f"Last saved {stamp}{by}")

    # ── Editable grid ──
    with edit_tab:
        st.markdown(
            'One dropdown per cell. Codes: **A** accountable, **R** responsible, '
            '**S** support, **C** consulted, **I** informed. Add `*` for tentative.'
        )

        grid = matrix_to_frame(matrix)
        column_config = {
            'Team member': st.column_config.TextColumn('Team member', width='medium', pinned=True),
        }
        for ws in matrix['workstreams']:
            column_config[ws] = st.column_config.SelectboxColumn(
                ws, options=ROLE_OPTIONS, required=False, width='small'
            )

        edited = st.data_editor(
            grid,
            column_config=column_config,
            hide_index=True,
            num_rows='dynamic',
            use_container_width=True,
            key='rasci_editor',
        )

        st.markdown('**Workstream signals**')
        signals = pd.DataFrame({
            'Workstream': matrix['workstreams'],
            'Visibility': [matrix['visibility'][ws] for ws in matrix['workstreams']],
            'Process dependency': [matrix['dependency'][ws] for ws in matrix['workstreams']],
        })
        edited_signals = st.data_editor(
            signals,
            column_config={
                'Workstream': st.column_config.TextColumn(disabled=True),
                'Visibility': st.column_config.SelectboxColumn(options=LEVELS, required=True),
                'Process dependency': st.column_config.SelectboxColumn(options=LEVELS, required=True),
            },
            hide_index=True,
            use_container_width=True,
            key='rasci_signal_editor',
        )

        save_col, revert_col, _ = st.columns([1, 1, 4])

        if save_col.button('Save changes', type='primary', key='rasci_save'):
            members, assignments = frame_to_assignments(edited, matrix['workstreams'])
            updated = {
                'members': members,
                'workstreams': matrix['workstreams'],
                'assignments': assignments,
                'visibility': dict(zip(edited_signals['Workstream'],
                                       edited_signals['Visibility'])),
                'dependency': dict(zip(edited_signals['Workstream'],
                                       edited_signals['Process dependency'])),
            }
            who = st.user.email if getattr(st.user, 'is_logged_in', False) else None
            try:
                save_matrix(updated, who)
                st.session_state['rasci_matrix'] = normalise_matrix(updated)
                st.success('Saved.')
                st.rerun()
            except OSError as exc:
                st.error(f"Couldn't write {MATRIX_PATH}: {exc}")

        if revert_col.button('Discard edits', key='rasci_revert'):
            st.session_state['rasci_matrix'] = load_matrix()
            st.rerun()

    # ── Structural changes ──
    with setup_tab:
        col_ws, col_person = st.columns(2)

        with col_ws:
            st.markdown('**Workstreams**')
            new_ws = st.text_input('Add a workstream', key='rasci_new_ws',
                                   placeholder='e.g. Restratification - AD')
            if st.button('Add workstream', key='rasci_add_ws'):
                name = new_ws.strip()
                if not name:
                    st.error('Give the workstream a name first.')
                elif name in matrix['workstreams']:
                    st.error(f'{name} is already in the matrix.')
                else:
                    matrix['workstreams'].append(name)
                    matrix['visibility'][name] = 'Low'
                    matrix['dependency'][name] = 'Low'
                    st.session_state['rasci_matrix'] = normalise_matrix(matrix)
                    st.rerun()

            drop_ws = st.multiselect('Remove workstreams', options=matrix['workstreams'],
                                     key='rasci_drop_ws')
            if st.button('Remove selected workstreams', key='rasci_rm_ws') and drop_ws:
                matrix['workstreams'] = [w for w in matrix['workstreams'] if w not in drop_ws]
                st.session_state['rasci_matrix'] = normalise_matrix(matrix)
                st.rerun()

        with col_person:
            st.markdown('**People**')
            try:
                known = sorted(load_data()['user_name'].dropna().unique())
                known = [n for n in known if n and n.lower() != 'nan'
                         and n not in matrix['members']]
            except Exception:
                known = []

            if known:
                st.caption(f"Logging time but not in the matrix: {', '.join(known)}")

            new_person = st.text_input('Add a person', key='rasci_new_person',
                                       placeholder='Name as it appears in the log')
            if st.button('Add person', key='rasci_add_person'):
                name = new_person.strip()
                if not name:
                    st.error('Give the person a name first.')
                elif name in matrix['members']:
                    st.error(f'{name} is already in the matrix.')
                else:
                    matrix['members'].append(name)
                    st.session_state['rasci_matrix'] = normalise_matrix(matrix)
                    st.rerun()

            drop_person = st.multiselect('Remove people', options=matrix['members'],
                                         key='rasci_drop_person')
            if st.button('Remove selected people', key='rasci_rm_person') and drop_person:
                matrix['members'] = [m for m in matrix['members'] if m not in drop_person]
                st.session_state['rasci_matrix'] = normalise_matrix(matrix)
                st.rerun()

        st.markdown('---')
        st.markdown('**Backup**')
        st.caption(
            'The matrix lives in a local JSON file, which a redeploy can wipe. '
            'Download a copy before any big change.'
        )
        b1, b2 = st.columns(2)
        b1.download_button(
            'Download matrix as JSON',
            data=json.dumps(normalise_matrix(matrix), indent=2),
            file_name='rasci_matrix.json',
            mime='application/json',
            key='rasci_download',
        )
        uploaded = b2.file_uploader('Restore from a JSON backup', type='json',
                                    key='rasci_upload')
        if uploaded is not None and st.button('Restore this file', key='rasci_restore'):
            try:
                restored = normalise_matrix(json.loads(uploaded.getvalue().decode('utf-8')))
                who = st.user.email if getattr(st.user, 'is_logged_in', False) else None
                save_matrix(restored, who)
                st.session_state['rasci_matrix'] = restored
                st.success('Restored.')
                st.rerun()
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as exc:
                st.error(f"That file isn't a valid matrix export: {exc}")


page_rasci()