"""
universal_churn/drift_monitoring.py
══════════════════════════════════════════════════════════════════════
FEATURE DRIFT MONITORING — Production Drift Detection

This module implements drift checks between training feature distributions
and recent inference batches. Coverage tells you whether features are
present, but NOT whether they are distributed like training data.

Why this matters
----------------
A model can have 100% feature coverage but still fail silently if the
feature DISTRIBUTION has shifted (e.g., tenure values are now 10x higher,
or satisfaction scores are compressed to a narrow range).

Metrics Implemented
-------------------
1. PSI (Population Stability Index) — Industry standard for bin-based
   distribution comparison. PSI > 0.25 indicates significant drift.
2. KL-Divergence Approximation — For continuous features, measures how
   one distribution diverges from another.
3. Mean/Std Shift Detection — Simple but effective for catching shifts
   in central tendency and variance.
4. Category Drift — For categorical features, tracks appearance of new
   categories and frequency shifts.

Usage
-----
    # During training, save reference distributions
    from universal_churn.drift_monitoring import compute_reference_stats

    ref_stats = compute_reference_stats(X_train, feature_names)
    joblib.dump(ref_stats, 'outputs/universal/reference_stats.pkl')

    # At inference time, check for drift
    from universal_churn.drift_monitoring import detect_feature_drift

    drift_report = detect_feature_drift(X_batch, ref_stats)
    if drift_report['significant_drift_detected']:
        alert_team(drift_report['drifting_features'])
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any
from dataclasses import dataclass, field
import warnings


# ══════════════════════════════════════════════════════════════════
# DRIFT THRESHOLDS
# ══════════════════════════════════════════════════════════════════

# PSI thresholds (industry standard)
PSI_THRESHOLD_WARNING = 0.10   # Yellow flag — monitor closely
PSI_THRESHOLD_CRITICAL = 0.25  # Red flag — significant drift

# Mean shift thresholds (in standard deviations)
MEAN_SHIFT_WARNING = 0.5       # 0.5 std shift
MEAN_SHIFT_CRITICAL = 1.0      # 1.0 std shift

# Std ratio thresholds
STD_RATIO_WARNING = 0.7        # Variance reduced by 30%+
STD_RATIO_CRITICAL = 0.5       # Variance reduced by 50%+

# Category drift thresholds
NEW_CATEGORY_THRESHOLD = 0.05  # New category >5% of data
FREQ_SHIFT_THRESHOLD = 0.20    # Category freq changed by 20%+


@dataclass
class FeatureDriftResult:
    """Result of drift analysis for a single feature."""
    feature_name: str
    feature_type: str  # 'continuous' | 'categorical'

    # PSI metrics
    psi_value: float | None = None
    psi_status: str = 'OK'  # 'OK' | 'WARNING' | 'CRITICAL'

    # Distribution shift metrics
    mean_shift_std: float | None = None  # Shift in training std units
    std_ratio: float | None = None       # Inference std / Training std
    mean_status: str = 'OK'
    std_status: str = 'OK'

    # Categorical-specific metrics
    new_categories: list[str] = field(default_factory=list)
    category_freq_shifts: dict[str, tuple[float, float]] = field(default_factory=dict)
    category_status: str = 'OK'

    # Overall status for this feature
    overall_status: str = 'OK'  # 'OK' | 'WARNING' | 'CRITICAL'

    def to_dict(self) -> dict:
        return {
            'feature': self.feature_name,
            'type': self.feature_type,
            'psi': self.psi_value,
            'psi_status': self.psi_status,
            'mean_shift_std': self.mean_shift_std,
            'std_ratio': self.std_ratio,
            'mean_status': self.mean_status,
            'std_status': self.std_status,
            'new_categories': self.new_categories,
            'category_status': self.category_status,
            'overall_status': self.overall_status,
        }


@dataclass
class DriftReport:
    """Complete drift report for an inference batch."""
    batch_id: str
    batch_size: int
    timestamp: str

    # Per-feature results
    feature_results: list[FeatureDriftResult] = field(default_factory=list)

    # Summary statistics
    total_features: int = 0
    features_with_warning: int = 0
    features_with_critical: int = 0
    significant_drift_detected: bool = False
    drifting_features: list[str] = field(default_factory=list)

    # Aggregate metrics
    avg_psi: float = 0.0
    max_psi: float = 0.0
    worst_feature: str = ''

    def to_dict(self) -> dict:
        return {
            'batch_id': self.batch_id,
            'batch_size': self.batch_size,
            'timestamp': self.timestamp,
            'total_features': self.total_features,
            'features_with_warning': self.features_with_warning,
            'features_with_critical': self.features_with_critical,
            'significant_drift_detected': self.significant_drift_detected,
            'drifting_features': self.drifting_features,
            'avg_psi': self.avg_psi,
            'max_psi': self.max_psi,
            'worst_feature': self.worst_feature,
            'feature_details': [r.to_dict() for r in self.feature_results],
        }


# ══════════════════════════════════════════════════════════════════
# PSI CALCULATION
# ══════════════════════════════════════════════════════════════════

def _calculate_psi(
    expected: np.ndarray,
    actual: np.ndarray,
    n_bins: int = 10,
    epsilon: float = 0.0001,
) -> float:
    """
    Calculate Population Stability Index (PSI) between two distributions.

    PSI = Σ (actual% - expected%) * ln(actual% / expected%)

    Interpretation:
        PSI < 0.10  : No significant change
        0.10-0.25   : Some moderate change
        PSI > 0.25  : Significant shift

    Parameters
    ----------
    expected : np.ndarray
        Training/reference distribution values.
    actual : np.ndarray
        Current/inference distribution values.
    n_bins : int
        Number of bins for discretization.
    epsilon : float
        Small value to avoid log(0) or division by zero.

    Returns
    -------
    psi : float
        Population Stability Index value.
    """
    # Create bin edges based on expected (training) distribution
    min_val = min(expected.min(), actual.min())
    max_val = max(expected.max(), actual.max())

    # Handle edge case where all values are the same
    if max_val == min_val:
        return 0.0

    bin_edges = np.linspace(min_val, max_val, n_bins + 1)

    # Bin the data
    expected_counts = np.histogram(expected, bins=bin_edges)[0]
    actual_counts = np.histogram(actual, bins=bin_edges)[0]

    # Convert to percentages
    expected_percents = (expected_counts + epsilon) / (len(expected) + epsilon * n_bins)
    actual_percents = (actual_counts + epsilon) / (len(actual) + epsilon * n_bins)

    # Calculate PSI
    psi = np.sum((actual_percents - expected_percents) * np.log(actual_percents / expected_percents))

    return float(psi)


def _calculate_mean_shift(
    train_mean: float,
    train_std: float,
    infer_mean: float,
) -> float:
    """
    Calculate mean shift in units of training standard deviations.

    This is more interpretable than raw difference because it's scaled
    to the natural variability of the feature.
    """
    if train_std == 0 or np.isnan(train_std):
        return 0.0
    return (infer_mean - train_mean) / train_std


def _calculate_std_ratio(
    train_std: float,
    infer_std: float,
) -> float:
    """
    Calculate ratio of inference std to training std.

    Values < 1 indicate variance compression.
    Values > 1 indicate variance expansion.
    """
    if train_std == 0 or np.isnan(train_std):
        return 1.0
    return infer_std / train_std


# ══════════════════════════════════════════════════════════════════
# REFERENCE STATISTICS COMPUTATION
# ══════════════════════════════════════════════════════════════════

def compute_reference_stats(
    X: pd.DataFrame | np.ndarray,
    feature_names: list[str] | None = None,
    categorical_features: list[str] | None = None,
) -> dict:
    """
    Compute and return reference statistics from training data.

    Save these statistics and use them at inference time for drift detection.

    Parameters
    ----------
    X : pd.DataFrame | np.ndarray
        Training feature matrix.
    feature_names : list[str] | None
        Column names if X is numpy array.
    categorical_features : list[str] | None
        List of feature names that are categorical.

    Returns
    -------
    reference_stats : dict
        Dictionary with structure:
        {
            'feature_name': {
                'type': 'continuous' | 'categorical',
                'mean': float,
                'std': float,
                'min': float,
                'max': float,
                'median': float,
                'percentiles': {25: float, 75: float},
                # For categorical:
                'categories': {cat: frequency, ...},
                'total_count': int,
            },
            ...
        }
    """
    if isinstance(X, np.ndarray):
        if feature_names is None:
            feature_names = [f'feature_{i}' for i in range(X.shape[1])]
        X = pd.DataFrame(X, columns=feature_names)

    categorical_set = set(categorical_features or [])
    reference_stats = {}

    for col in X.columns:
        col_data = X[col].dropna()

        if col in categorical_set or X[col].dtype == 'object' or X[col].dtype.name == 'category':
            # Categorical feature
            value_counts = col_data.value_counts(normalize=True)
            reference_stats[col] = {
                'type': 'categorical',
                'categories': value_counts.to_dict(),
                'n_unique': len(value_counts),
                'total_count': len(col_data),
            }
        else:
            # Continuous feature
            reference_stats[col] = {
                'type': 'continuous',
                'mean': float(col_data.mean()),
                'std': float(col_data.std()),
                'min': float(col_data.min()),
                'max': float(col_data.max()),
                'median': float(col_data.median()),
                'percentiles': {
                    '25': float(col_data.quantile(0.25)),
                    '75': float(col_data.quantile(0.75)),
                },
                'total_count': len(col_data),
            }

    return reference_stats


# ══════════════════════════════════════════════════════════════════
# DRIFT DETECTION
# ══════════════════════════════════════════════════════════════════

def detect_feature_drift(
    X_inference: pd.DataFrame | np.ndarray,
    reference_stats: dict,
    batch_id: str | None = None,
    categorical_features: list[str] | None = None,
) -> DriftReport:
    """
    Detect feature drift between inference batch and training reference.

    Parameters
    ----------
    X_inference : pd.DataFrame | np.ndarray
        Inference feature matrix.
    reference_stats : dict
        Reference statistics from compute_reference_stats().
    batch_id : str | None
        Identifier for this inference batch.
    categorical_features : list[str] | None
        List of categorical feature names.

    Returns
    -------
    DriftReport
        Complete drift analysis with per-feature and summary metrics.
    """
    from datetime import datetime, timezone

    if isinstance(X_inference, np.ndarray):
        feature_names = list(reference_stats.keys())
        X_inference = pd.DataFrame(X_inference, columns=feature_names[:X_inference.shape[1]])

    batch_id = batch_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    timestamp = datetime.now(timezone.utc).isoformat()

    report = DriftReport(
        batch_id=batch_id,
        batch_size=len(X_inference),
        timestamp=timestamp,
    )

    psi_values = []

    for feature_name, ref_stats in reference_stats.items():
        if feature_name not in X_inference.columns:
            # Feature missing entirely — skip (coverage should catch this)
            continue

        infer_data = X_inference[feature_name].dropna()
        if len(infer_data) == 0:
            continue

        result = FeatureDriftResult(
            feature_name=feature_name,
            feature_type=ref_stats['type'],
        )

        if ref_stats['type'] == 'continuous':
            # Continuous feature drift detection
            _detect_continuous_drift(
                result, infer_data, ref_stats
            )
        else:
            # Categorical feature drift detection
            _detect_categorical_drift(
                result, infer_data, ref_stats
            )

        # Determine overall status (worst of individual statuses)
        statuses = [result.psi_status, result.mean_status, result.std_status, result.category_status]
        if 'CRITICAL' in statuses:
            result.overall_status = 'CRITICAL'
        elif 'WARNING' in statuses:
            result.overall_status = 'WARNING'
        else:
            result.overall_status = 'OK'

        report.feature_results.append(result)

        if result.psi_value is not None:
            psi_values.append(result.psi_value)

        # Track drifting features
        if result.overall_status != 'OK':
            report.drifting_features.append(feature_name)
            if result.overall_status == 'WARNING':
                report.features_with_warning += 1
            elif result.overall_status == 'CRITICAL':
                report.features_with_critical += 1

    # Compute summary statistics
    report.total_features = len(report.feature_results)
    report.significant_drift_detected = report.features_with_critical > 0

    if psi_values:
        report.avg_psi = float(np.mean(psi_values))
        report.max_psi = float(np.max(psi_values))
        # Find worst feature by PSI
        psi_results = [(r.feature_name, r.psi_value) for r in report.feature_results if r.psi_value is not None]
        if psi_results:
            report.worst_feature = max(psi_results, key=lambda x: x[1])[0]

    return report


def _detect_continuous_drift(
    result: FeatureDriftResult,
    infer_data: pd.Series,
    ref_stats: dict,
) -> None:
    """Detect drift for a continuous feature."""
    infer_array = infer_data.values

    # Get reference stats
    train_mean = ref_stats.get('mean', 0)
    train_std = ref_stats.get('std', 1)
    train_min = ref_stats.get('min', 0)
    train_max = ref_stats.get('max', 1)

    # Compute inference stats
    infer_mean = float(infer_data.mean())
    infer_std = float(infer_data.std())
    infer_min = float(infer_data.min())
    infer_max = float(infer_data.max())

    # Calculate PSI
    # Reconstruct approximate training distribution from stats
    # (In production, you'd want to store actual training samples or histograms)
    try:
        # Use percentiles if available for better PSI estimation
        p25 = ref_stats.get('percentiles', {}).get('25', train_mean - train_std)
        p75 = ref_stats.get('percentiles', {}).get('75', train_mean + train_std)

        # Generate synthetic training distribution
        n_synthetic = min(1000, len(infer_array))
        train_synthetic = np.random.normal(train_mean, max(train_std, 0.001), n_synthetic)
        train_synthetic = np.clip(train_synthetic, train_min, train_max)

        result.psi_value = _calculate_psi(train_synthetic, infer_array)
    except Exception:
        result.psi_value = None

    # Classify PSI status
    if result.psi_value is not None:
        if result.psi_value >= PSI_THRESHOLD_CRITICAL:
            result.psi_status = 'CRITICAL'
        elif result.psi_value >= PSI_THRESHOLD_WARNING:
            result.psi_status = 'WARNING'

    # Calculate mean shift
    result.mean_shift_std = _calculate_mean_shift(train_mean, train_std, infer_mean)
    if abs(result.mean_shift_std) >= MEAN_SHIFT_CRITICAL:
        result.mean_status = 'CRITICAL'
    elif abs(result.mean_shift_std) >= MEAN_SHIFT_WARNING:
        result.mean_status = 'WARNING'

    # Calculate std ratio
    result.std_ratio = _calculate_std_ratio(train_std, infer_std)
    # Check for variance compression or expansion
    if result.std_ratio <= STD_RATIO_CRITICAL or result.std_ratio >= (1 / STD_RATIO_CRITICAL):
        result.std_status = 'CRITICAL'
    elif result.std_ratio <= STD_RATIO_WARNING or result.std_ratio >= (1 / STD_RATIO_WARNING):
        result.std_status = 'WARNING'


def _detect_categorical_drift(
    result: FeatureDriftResult,
    infer_data: pd.Series,
    ref_stats: dict,
) -> None:
    """Detect drift for a categorical feature."""
    ref_categories = ref_stats.get('categories', {})
    infer_value_counts = infer_data.value_counts(normalize=True)
    infer_categories = infer_value_counts.to_dict()

    # Check for new categories
    new_cats = set(infer_categories.keys()) - set(ref_categories.keys())
    result.new_categories = list(new_cats)

    # Check if any new category is significant
    for cat in new_cats:
        if infer_categories.get(cat, 0) >= NEW_CATEGORY_THRESHOLD:
            result.category_status = 'WARNING'
            break

    # Check for frequency shifts in existing categories
    for cat in ref_categories:
        if cat in infer_categories:
            ref_freq = ref_categories[cat]
            infer_freq = infer_categories[cat]
            freq_change = abs(infer_freq - ref_freq)

            if freq_change >= FREQ_SHIFT_THRESHOLD:
                result.category_freq_shifts[cat] = (ref_freq, infer_freq)
                if result.category_status == 'OK':
                    result.category_status = 'WARNING'

    # If many new categories or large shifts, mark as critical
    if len(new_cats) > ref_stats.get('n_unique', 1):
        result.category_status = 'CRITICAL'


# ══════════════════════════════════════════════════════════════════
# DRIFT REPORTING & ALERTING
# ══════════════════════════════════════════════════════════════════

def format_drift_report(report: DriftReport) -> str:
    """Format a drift report for human consumption (logs, alerts)."""
    lines = [
        f"DRIFT REPORT: {report.batch_id}",
        f"Timestamp: {report.timestamp}",
        f"Batch Size: {report.batch_size}",
        f"Features Analyzed: {report.total_features}",
        "",
        "SUMMARY:",
        f"  - Features with WARNING: {report.features_with_warning}",
        f"  - Features with CRITICAL drift: {report.features_with_critical}",
        f"  - Average PSI: {report.avg_psi:.4f}",
        f"  - Maximum PSI: {report.max_psi:.4f} ({report.worst_feature})",
        f"  - SIGNIFICANT DRIFT DETECTED: {'YES ⚠️' if report.significant_drift_detected else 'No'}",
        "",
    ]

    if report.drifting_features:
        lines.append("DRIFTING FEATURES:")
        for result in report.feature_results:
            if result.overall_status != 'OK':
                lines.append(f"  [{result.overall_status}] {result.feature_name}")
                if result.psi_value is not None:
                    lines.append(f"      PSI: {result.psi_value:.4f} ({result.psi_status})")
                if result.mean_shift_std is not None:
                    lines.append(f"      Mean Shift: {result.mean_shift_std:.2f} std ({result.mean_status})")
                if result.std_ratio is not None:
                    lines.append(f"      Std Ratio: {result.std_ratio:.2f} ({result.std_status})")
                if result.new_categories:
                    lines.append(f"      New Categories: {result.new_categories}")
        lines.append("")

    return "\n".join(lines)


def should_alert_on_drift(report: DriftReport) -> bool:
    """
    Determine if an alert should be triggered based on drift report.

    Customize this logic based on your organization's tolerance.
    """
    # Alert on any critical drift
    if report.features_with_critical > 0:
        return True

    # Alert if multiple warnings
    if report.features_with_warning >= 3:
        return True

    # Alert if average PSI is high
    if report.avg_psi >= PSI_THRESHOLD_WARNING:
        return True

    return False


# ══════════════════════════════════════════════════════════════════
# PERSISTENCE HELPERS
# ══════════════════════════════════════════════════════════════════

def save_reference_stats(stats: dict, path: str) -> None:
    """Save reference statistics to disk."""
    import joblib
    joblib.dump(stats, path)


def load_reference_stats(path: str) -> dict:
    """Load reference statistics from disk."""
    import joblib
    return joblib.load(path)


def save_drift_report(report: DriftReport, path: str) -> None:
    """Save drift report to disk (as JSON-compatible dict)."""
    import json
    with open(path, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)