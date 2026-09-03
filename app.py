import streamlit as st

st.set_page_config(page_title=" EQ <> GC Progress Monitor Hub", layout="wide")

st.markdown("""
    <style>
    .stApp {
        background-color: #00011b;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    header[data-testid="stHeader"] {
        background-color: #ffffff00;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #000120;
    }
    </style>
""", unsafe_allow_html=True)

st.logo("https://github.com/nikhil-eq/comprehensive-project-management/blob/main/eq%20-%20white.png?raw=true", size = 'medium', )
st.title('EQ <> GC Progress Monitor Hub')

pg = st.navigation([st.Page("daily_entry.py", title = 'Daily Log Entry'), 
                    st.Page("weekly_view.py", title = 'Weekly Progress'), 
                    st.Page("monthly_view.py", title = 'Monthly Progress'),
                    st.Page('delivered_view.py', title = 'Lifetime Progress'), 
                    st.Page('efficiency_view.py', title = "Efficiencies"), 
                    st.Page('rnd_view.py', title = "R&D")])

pg.run()
