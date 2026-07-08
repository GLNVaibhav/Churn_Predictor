import streamlit as st

from components.cards import (
    analysis_wizard,
    framework_status,
    hero_card,
    metric_card,
    recent_analyses_card,
    updates_card,
)
from pages.workspace import workspace_page
from utils.session import get_session_state


def dashboard():
    state = get_session_state()

    if state.get("view") == "workspace":
        workspace_page()
        return

    hero_card()

    st.write("")

    if state.get("view") == "wizard":
        analysis_wizard()
        return

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        metric_card("Framework", "Healthy", "🟢", "Operational")

    with c2:
        metric_card("Models", "8", "🧠", "Loaded")

    with c3:
        metric_card("Knowledge", "Ready", "📚", "Updated")

    with c4:
        metric_card("Version", "v8", "🚀", "Latest")

    st.divider()

    left, right = st.columns([2, 1])

    with left:
        recent_analyses_card()

    with right:
        framework_status()

    st.divider()

    a, b = st.columns(2)

    with a:
        updates_card()

    with b:
        st.info(
            """
### Quick Insights

• Universal Framework Loaded

• Routing Engine Ready

• Coverage Engine Active

• Knowledge Base Loaded

• Business Reasoning Available
"""
        )
