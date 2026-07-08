import streamlit as st


def get_session_state():
    state = st.session_state
    state.setdefault("view", "home")
    state.setdefault("wizard_step", 1)
    state.setdefault("current_analysis", None)
    return state
