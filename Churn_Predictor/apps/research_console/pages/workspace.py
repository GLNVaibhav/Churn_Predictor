import pandas as pd
import streamlit as st

from components.cards import pipeline_status_card
from utils.session import get_session_state


def workspace_page():
    state = get_session_state()
    analysis_id = state.get("current_analysis", "A1026")

    st.title(f"Analysis #{analysis_id}")
    st.subheader("Workspace")
    st.caption("Framework Integration")

    tabs = st.tabs(
        [
            "Overview",
            "Pipeline",
            "Coverage",
            "Quality",
            "Routing",
            "Prediction",
            "Reasoning",
            "Decision",
            "Reports",
        ]
    )

    with tabs[0]:
        st.metric("Status", "Completed")
        st.metric("Industry", "Telecom")
        st.metric("Coverage", "Enabled")

    with tabs[1]:
        pipeline_status_card()

    with tabs[2]:
        st.dataframe(
            pd.DataFrame({"Feature": ["Tenure", "Usage", "Support"], "Covered": [True, True, True]}),
            use_container_width=True,
        )

    with tabs[3]:
        st.info("Quality checks passed.")

    with tabs[4]:
        st.success("Routing engine active.")

    with tabs[5]:
        st.write("Prediction output ready.")

    with tabs[6]:
        st.write("Reasoning traces available.")

    with tabs[7]:
        st.write("Decision summary available.")

    with tabs[8]:
        st.write("Reports generated.")
