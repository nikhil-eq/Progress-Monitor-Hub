import streamlit as st

# --------------------------------------------------
#              PAGE CONFIG (once only)
# --------------------------------------------------
st.set_page_config(page_title="EQ <> GC Progress Monitor Hub", layout="wide")

# --------------------------------------------------
#         ANIMATED BACKGROUND + THEME CSS
# --------------------------------------------------
st.markdown("""
    <style>
    /* Main app: animated dark gradient */
    .stApp {
        background: linear-gradient(-45deg, #016c59, #000000, #016c59);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
    }

    /* Sidebar: same animated gradient */
    [data-testid="stSidebar"] {
        background: linear-gradient(-45deg, #016c59, #000000, #016c59);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
    }

    /* Header: fully transparent so the gradient shows through */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }

    @keyframes gradientShift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* Keep text readable on dark animated backgrounds */
    .stApp, p, h1, h2, h3, h4, h5, h6, li, span, label, .stMarkdown {
        color: #ffffff !important;
    }
    </style>
""", unsafe_allow_html=True)

# --------------------------------------------------
#              IDENTITY & ACCESS CONTROL
# --------------------------------------------------
# Admin allowlist lives in st.secrets (never in the repo):
#   admin_emails = ["nikhil@equilibriumearth.com", ...]
admin_emails = set(st.secrets.get("admin_emails", []))

user_email = st.user.email if st.user.is_logged_in else None
is_admin = bool(user_email and user_email.lower() in {e.lower() for e in admin_emails})

# --------------------------------------------------
#              BRANDING
# --------------------------------------------------
st.logo(
    "https://github.com/nikhil-eq/comprehensive-project-management/blob/main/eq%20-%20white.png?raw=true",
    size='medium',
)
st.title('EQ <> GC Progress Monitor Hub')

# --------------------------------------------------
#              LOGIN / LOGOUT (sidebar)
# --------------------------------------------------
with st.sidebar:
    st.markdown("---")
    # st.markdown("### 🔒 Admin Reports")

    if not st.user.is_logged_in:
        st.markdown("Sign in with Google to unlock the admin reports.")
        st.login()  # renders the "Log in with Google" button
    else:
        st.markdown(f"Signed in as: `{user_email}`")
        if is_admin:
            st.success("Admin access granted 🗸")
        else:
            st.info("Standard access — admin reports are hidden.")
        if st.button("Log out"):
            st.logout()

# --------------------------------------------------
#              PAGE ROUTING
# --------------------------------------------------
public_pages = [
    st.Page("daily_entry.py", title='Daily Log Entry'),
    st.Page("weekly_view.py", title='Weekly Snapshot'),
]

restricted_pages = [
    st.Page("monthly_view.py", title='Monthly Recap'),
    st.Page("delivered_view.py", title='Delivered - Since Inception'),
    st.Page('efficiency_view.py', title="Lean Improvements"),
    st.Page('rnd_view.py', title="R&D"),
    st.Page('project_journey_view.py', title="Project Journey"),
]

pages = public_pages + restricted_pages if is_admin else public_pages

pg = st.navigation(pages)
pg.run()