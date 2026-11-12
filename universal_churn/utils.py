"""
universal_churn/utils.py
Small shared utilities used across multiple modules.
"""
from __future__ import annotations
from datetime import datetime, timezone
import numpy as np


def _utc_timestamp() -> str:
    """Return current UTC time as a formatted string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def prediction_confidence_label(probability: float) -> str:
    """Confidence in the prediction score itself (not the probability magnitude)."""
    if probability > 0.90:
        return "Very High"
    elif probability >= 0.75:
        return "High"
    elif probability >= 0.60:
        return "Medium"
    elif probability >= 0.40:
        return "Low"
    return "Very Low"


def coverage_confidence_label(coverage_score: float) -> str:
    """Map coverage score to a reliability label."""
    pct = coverage_score * 100
    if pct >= 95:
        return "Excellent"
    elif pct >= 85:
        return "Good"
    elif pct >= 70:
        return "Moderate"
    elif pct >= 60:
        return "Poor"
    return "Insufficient"


def positive_class_probabilities(model, features) -> np.ndarray:
    """Return validated probabilities for the normalized churn-positive class (1).

    Scikit-learn orders probability columns according to ``classes_``; relying
    on column 1 alone silently changes meaning if a persisted estimator has a
    different class order. UCIF normalizes churn labels to integer 0/1, so the
    positive event is explicitly class 1.
    """
    classes = np.asarray(getattr(model, "classes_", []))
    if classes.size != 2 or set(classes.tolist()) != {0, 1}:
        raise ValueError("Churn model must expose binary classes labeled 0 and 1.")
    positive_indices = np.flatnonzero(classes == 1)

    probabilities = np.asarray(model.predict_proba(features), dtype=float)
    expected_rows = len(features)
    if probabilities.ndim != 2 or probabilities.shape != (expected_rows, len(classes)):
        raise ValueError("Churn model returned probabilities with an unexpected shape.")
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Churn model returned non-finite or out-of-range probabilities.")
    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("Churn model returned probability rows that do not sum to one.")

    positive = probabilities[:, int(positive_indices[0])]
    return positive


def verify_prediction_variance(probabilities: np.ndarray,
                               threshold: float = 1e-4) -> None:
    """
    Diagnostic guard against silent flatlining (every row getting ~the same
    probability), which is the symptom of a schema-misalignment bug.
    """
    if len(probabilities) > 1 and np.std(probabilities) < threshold:
        raise RuntimeError(
            f"CRITICAL WARNING: Model outputs show ~zero variance "
            f"(std={np.std(probabilities):.6f} < {threshold}). "
            f"Input features likely misaligned with training schema."
        )
