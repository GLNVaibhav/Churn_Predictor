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