import streamlit as st

from pages.dashboard import dashboard


st.set_page_config(
    page_title="UCIF",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


dashboard()
