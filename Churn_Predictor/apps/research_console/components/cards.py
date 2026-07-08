import pandas as pd
import time
import streamlit as st

from services.execution_service import run_execution
from utils.session import get_session_state


def hero_card():
    state = get_session_state()

    st.markdown(
        """
# 🧠 UCIF Research Console

### Enterprise AI Decision Intelligence Platform

Analyze customer churn through
Universal AI,
Coverage Intelligence,
Business Reasoning,
Adaptive Routing,
and Explainable AI.
"""
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("🚀 New Analysis", use_container_width=True):
            state["view"] = "wizard"
            st.rerun()

    with c2:
        st.button("📂 Sample Dataset", use_container_width=True)

    with c3:
        st.button("📑 Documentation", use_container_width=True)

    with c4:
        st.button("📊 Reports", use_container_width=True)


def metric_card(title, value, icon, footer):
    st.metric(label=f"{icon} {title}", value=value)
    st.caption(footer)


def execution_table():
    df = pd.DataFrame(
        {
            "Execution": ["EX-1021", "EX-1020", "EX-1019", "EX-1018"],
            "Industry": ["Telecom", "Banking", "Insurance", "SaaS"],
            "Status": ["Completed", "Completed", "Running", "Completed"],
            "Risk": ["High", "Medium", "Low", "High"],
        }
    )

    st.subheader("Recent Executions")
    st.dataframe(df, use_container_width=True)


def framework_status():
    st.subheader("Framework Status")

    st.success("Universal Framework")
    st.success("Knowledge Base")
    st.success("Coverage Engine")
    st.success("Routing Engine")
    st.success("Business Reasoning")


def updates_card():
    st.subheader("Release Notes")
    st.markdown(
        """

### Version 8

✔ Universal Pipeline

✔ Knowledge Intelligence

✔ Coverage Intelligence

✔ Adaptive Routing

✔ Business Reasoning

✔ Decision Intelligence

"""
    )


def recent_analyses_card():
    df = pd.DataFrame(
        {
            "Analysis": ["A1025", "A1024", "A1023"],
            "Industry": ["Telecom", "Banking", "Retail"],
            "Status": ["Completed", "Completed", "Running"],
            "Model": ["XGBoost", "Random Forest", "Logistic Regression"],
        }
    )

    st.subheader("Recent Analyses")
    st.dataframe(df, use_container_width=True)


def analysis_wizard():
    state = get_session_state()

    st.subheader("Analysis Wizard")
    st.caption("Step 1 Upload Dataset → Step 2 Preview → Step 3 Industry Detection → Step 4 Coverage → Step 5 Execute")

    step = state.get("wizard_step", 1)
    progress = (step - 1) / 4 if step > 1 else 0
    st.progress(progress)

    step_labels = [
        "Step 1 Upload Dataset",
        "Step 2 Preview",
        "Step 3 Industry Detection",
        "Step 4 Coverage",
        "Step 5 Execute",
    ]
    st.write(step_labels[step - 1])

    if step == 1:
        st.file_uploader("Upload Dataset")
        if st.button("Continue to Preview", type="primary"):
            state["wizard_step"] = 2
            st.rerun()

    elif step == 2:
        st.dataframe(
            pd.DataFrame(
                {
                    "CustomerID": [101, 102, 103],
                    "Tenure": [12, 8, 23],
                    "Churn": [0, 1, 0],
                }
            ),
            use_container_width=True,
        )
        if st.button("Continue to Industry Detection", type="primary"):
            state["wizard_step"] = 3
            st.rerun()

    elif step == 3:
        st.info("Industry Detection: Telecom")
        if st.button("Continue to Coverage", type="primary"):
            state["wizard_step"] = 4
            st.rerun()

    elif step == 4:
        st.success("Coverage: Enabled")
        if st.button("Continue to Execute", type="primary"):
            state["wizard_step"] = 5
            st.rerun()

    else:
        pipeline = st.empty()
        for value in range(0, 101, 20):
            pipeline.progress(value)
            time.sleep(0.08)

        result = run_execution()
        state["current_analysis"] = result["analysis_id"]
        state["view"] = "workspace"
        state["wizard_step"] = 1
        st.rerun()


def pipeline_status_card():
    st.subheader("Pipeline")
    for label in ["Upload", "Preview", "Industry Detection", "Coverage", "Execute"]:
        st.status(label, state="complete")
