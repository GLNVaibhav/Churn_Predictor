"""
universal_churn/explainability.py
SHAP-based explanation logging and summary.
shap is an optional dependency — all functions degrade gracefully if
it isn't installed.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False


def write_shap_log(
    model,
    X_df: pd.DataFrame,
    feature_names: list[str],
    id_values: np.ndarray | None,
    output_path: str,
    top_n: int = 3,
) -> None:
    """
    Write a per-row SHAP explanation CSV so analysts can see which
    features drove each customer's churn probability.
    """
    if not SHAP_AVAILABLE:
        print("  WARNING: shap not installed — skipping explanation log. "
              "Run `pip install shap` to enable --explain.")
        return

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_df[feature_names])
    except Exception as exc:
        print(f"  WARNING: SHAP explanation failed ({exc}); skipping log.")
        return

    rows = []
    for i in range(len(X_df)):
        row_shap = shap_values[i]
        order = np.argsort(-np.abs(row_shap))[:top_n]
        record = {'CustomerID': id_values[i] if id_values is not None else i}
        for rank, idx in enumerate(order, start=1):
            record[f'top{rank}_feature'] = feature_names[idx]
            record[f'top{rank}_shap_value'] = round(float(row_shap[idx]), 4)
        rows.append(record)

    log_df = pd.DataFrame(rows)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    log_df.to_csv(output_path, index=False)
    print(f"  SHAP explanation log saved: {output_path}")


def summarize_shap_directions(
    model,
    X_df: pd.DataFrame,
    feature_names: list[str],
    top_n: int = 3,
) -> dict | None:
    """
    Aggregate dataset-wide SHAP summary: top features increasing and
    decreasing churn probability across all rows.
    """
    if not SHAP_AVAILABLE:
        return None
    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_df[feature_names])
    except Exception:
        return None

    mean_contrib = np.mean(shap_values, axis=0)
    order = np.argsort(mean_contrib)

    increasing = [feature_names[i] for i in order[::-1] if mean_contrib[i] > 0][:top_n]
    decreasing = [feature_names[i] for i in order if mean_contrib[i] < 0][:top_n]

    return {'top_increasing': increasing, 'top_decreasing': decreasing}