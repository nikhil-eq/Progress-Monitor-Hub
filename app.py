import streamlit as st
import hashlib

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
# CHANGE THESE PASSWORDS before deploying
# Format: "email": "hashed_password"  (SHA-256 for basic obfuscation)
ALLOWED_USERS = {
    "nikhil@equilibriumearth.com": hashlib.sha256("Nikhil@2000".encode()).hexdigest(),
    "sri@equilibriumearth.com": hashlib.sha256("sri@15".encode()).hexdigest(),
    "subhadeep@equilibriumearth.com": hashlib.sha256("subhadeep@17".encode()).hexdigest(),
    "samreen@equilibriumearth.com": hashlib.sha256("samreen@17".encode()).hexdigest(),
}

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.auth_email = None

with st.sidebar:
    st.markdown("---")
    st.markdown("### 🔒 Admin Reports")

    if not st.session_state.authenticated:
        email = st.text_input("Email", key="login_email", placeholder="admin@company.com")
        password = st.text_input("Password", type="password", key="login_pwd", placeholder="••••••••")

        if st.button("Unlock", key="auth_unlock_btn"):
            clean_email = email.strip().lower()
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()

            if clean_email in ALLOWED_USERS and ALLOWED_USERS[clean_email] == pwd_hash:
                st.session_state.authenticated = True
                st.session_state.auth_email = clean_email
                st.rerun()
            else:
                st.error("❌ Invalid email or password")
    else:
        st.markdown(f"🔓 **Admin:** `{st.session_state.auth_email}`")
        if st.button("Logout", key="auth_logout_btn"):
            st.session_state.authenticated = False
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

# Pages locked behind REAL authentication
restricted_pages = [
    st.Page("monthly_view.py", title='Monthly Progress'),
    st.Page("delivered_view.py", title='Lifetime Progress'),
    st.Page('efficiency_view.py', title="Efficiencies"),
]

pages = public_pages + restricted_pages if st.session_state.authenticated else public_pages

pg = st.navigation(pages)
pg.run()