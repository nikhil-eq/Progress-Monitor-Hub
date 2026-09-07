import streamlit as st

st.set_page_config(page_title=" EQ <> GC Progress Monitor Hub", layout="wide")

# ── Your existing CSS ──
st.markdown("""
    <style>
    .stApp { background-color: #00011b; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    header[data-testid="stHeader"] { background-color: #ffffff00; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #000120; }
    </style>
""", unsafe_allow_html=True)

# ==================== ACCESS CONTROL ====================
ALLOWED_EMAILS = ["nikhil@equilibriumearth.com",
                  "sri@equilibriumearth.com", 
                  "subhadeep@equilibriumearth.com"]   # <-- CHANGE THIS

if "auth_email" not in st.session_state:
    st.session_state.auth_email = None

with st.sidebar:
    if st.session_state.auth_email is None:
        st.markdown("---")
        st.markdown("### 🔒 Admin Reports")
        email = st.text_input("Email", key="auth_email_input",
                              placeholder="Enter admin email…")
        if st.button("Unlock", key="auth_unlock_btn"):
            if email.strip().lower() in [e.lower() for e in ALLOWED_EMAILS]:
                st.session_state.auth_email = email.strip().lower()
                st.rerun()
            else:
                st.error("❌ Access denied")
    else:
        st.markdown("---")
        st.markdown(f"🔓 **Admin:** `{st.session_state.auth_email}`")
        if st.button("Logout", key="auth_logout_btn"):
            st.session_state.auth_email = None
            st.rerun()
# =======================================================

st.logo("https://github.com/nikhil-eq/comprehensive-project-management/blob/main/eq%20-%20white.png?raw=true", size='medium')
st.title('EQ <> GC Progress Monitor Hub')

# Pages everyone can see
public_pages = [
    st.Page("daily_entry.py", title='Daily Log Entry'),
    st.Page("weekly_view.py", title='Weekly Progress'),
    st.Page('rnd_view.py', title="R&D"),
]

# Pages locked behind email
restricted_pages = [
    st.Page("monthly_view.py", title='Monthly Progress'),
    st.Page('delivered_view.py', title='Lifetime Progress'),
    st.Page('efficiency_view.py', title="Efficiencies"),
]

pages = public_pages + restricted_pages if st.session_state.auth_email else public_pages

pg = st.navigation(pages)
pg.run()