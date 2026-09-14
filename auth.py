import streamlit as st

# Hard-coded list (easy to swap for st.secrets later)
ALLOWED_EMAILS = ['nikhil@equilibriumearth.com']   # <-- CHANGE THIS

def require_auth():
    """Stop the page if the user hasn't authenticated."""
    authorised = st.session_state.get("auth_email") in [e for e in ALLOWED_EMAILS]
    if not authorised:
        st.error("🔒 Access denied — this report is restricted.")
        st.info("Enter the admin email in the sidebar to unlock.")
        st.stop()