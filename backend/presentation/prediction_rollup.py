"""
backend.presentation.prediction_rollup
══════════════════════════════════════════════════════════════════════
Type-B presentation aggregation for prediction KPI cards.

Counts, averages, and risk distributions derived from per-row
framework output are presentation concerns — they belong here, not in
``FrameworkMapper`` (pure translation) or ``universal_churn`` (Type-A
business intelligence).
"""
from __future__ import annotations

from typing import Any, Optional

from ..contracts.analysis_response import PredictionSummary
from ..exceptions import UnsupportedFrameworkOutputError


def build_prediction_summary(results: Optional[Any]) -> Optional[PredictionSummary]:
    """
    Build a ``PredictionSummary`` from a framework results DataFrame.

    This is presentation aggregation only — every value is read from
    columns the framework already computed per row.
    """
    if results is None:
        return None
    try:
        n_rows = len(results)
    except TypeError as exc:
        raise UnsupportedFrameworkOutputError(
            "build_prediction_summary() expects a DataFrame-like object "
            "(supports len()) with Predicted_Churn/Churn_Probability/"
            "Risk_Level/Prediction_Model/Prediction_Mode columns."
        ) from exc
    if n_rows == 0:
        return PredictionSummary(rows=0)

    churn_col = results["Predicted_Churn"] if "Predicted_Churn" in results.columns else None
    prob_col = results["Churn_Probability"] if "Churn_Probability" in results.columns else None
    risk_col = results["Risk_Level"] if "Risk_Level" in results.columns else None

    predicted_churners = int((churn_col == "Yes").sum()) if churn_col is not None else 0
    average_probability = float(prob_col.mean()) if prob_col is not None else 0.0
    risk_distribution = (
        {str(k): int(v) for k, v in risk_col.value_counts().to_dict().items()}
        if risk_col is not None else {}
    )
    prediction_model = (
        str(results["Prediction_Model"].iloc[0])
        if "Prediction_Model" in results.columns else None
    )
    prediction_mode = (
        str(results["Prediction_Mode"].iloc[0])
        if "Prediction_Mode" in results.columns else None
    )

    return PredictionSummary(
        rows=n_rows,
        predicted_churners=predicted_churners,
        average_probability=round(average_probability, 4),
        risk_distribution=risk_distribution,
        prediction_model=prediction_model,
        prediction_mode=prediction_mode,
    )
