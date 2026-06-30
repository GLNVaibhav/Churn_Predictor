"""
universal_churn.quality_gate
=============================
Information Quality Engine — runs INDEPENDENTLY of coverage scoring.

Why this is a separate module from coverage.py
-------------------------------------------------
The architecture review flagged that coverage.py was conflating two
different questions into one number:

    Coverage check : is the concept/feature POPULATED at all?
    Quality check   : is the populated value TRUSTWORTHY?

coverage.py already does a *light* version of the quality check inline
(null rate >= 95%, constant/no-variance columns are scored quality=0).
That inline check is good but incomplete — it does NOT check for
target leakage, the exact failure mode that broke the original
Healthcare dataset (BMI correlated 1.0 with Churn, producing a
suspicious 100% accuracy model — see project history).

This module is the dedicated, more thorough quality engine:

    1. Null rate check        (already partially in coverage.py;
                                reimplemented here with explicit
                                thresholds so it's independently
                                testable and reusable outside the
                                coverage-scoring code path)
    2. Variance check         (constant / near-constant columns)
    3. Target leakage check   (correlation between a candidate
                                feature and the target column —
                                THIS is the new check coverage.py
                                never had)

Relationship to coverage.py
-----------------------------
quality_gate.py does NOT replace or modify compute_coverage_score().
It is called separately, before or alongside coverage scoring, and
its findings (especially leakage) should make a human stop and
re-examine the dataset — exactly as happened with the original
Healthcare BMI incident. A leaked column should never silently
contribute to coverage as if it were a normal high-quality feature.

Typical usage
-------------
    from universal_churn.quality_gate import run_quality_gate

    quality_report = run_quality_gate(df_input, target_col='Churn')
    if quality_report['leakage_detected']:
        # surface a hard warning in the CLI / report before training
        # or before trusting a sector model's coverage score
        ...
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# ══════════════════════════════════════════════════════════════════
# THRESHOLDS
# ══════════════════════════════════════════════════════════════════
# These are deliberately separate constants from coverage.py's
# green/yellow/red thresholds — quality and coverage are different
# axes and should be tunable independently.

NULL_RATE_THRESHOLD       = 0.95   # >= this fraction null -> fails quality
NEAR_CONSTANT_THRESHOLD   = 1      # <= this many unique non-null values -> fails
LEAKAGE_CORRELATION_HIGH  = 0.95   # |corr| >= this with target -> leakage flag
LEAKAGE_CORRELATION_WARN  = 0.80   # |corr| >= this -> soft warning, not hard flag


# ══════════════════════════════════════════════════════════════════
# RESULT STRUCTURES
# ══════════════════════════════════════════════════════════════════

@dataclass
class ColumnQualityResult:
    column: str
    passed: bool
    null_rate: float
    n_unique: int
    is_near_constant: bool
    target_correlation: float | None = None   # None if not numeric / no target
    leakage_flag: bool = False
    leakage_warning: bool = False
    reasons: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
# INDIVIDUAL CHECKS
# ══════════════════════════════════════════════════════════════════

def _check_null_rate(series: pd.Series) -> tuple[bool, float]:
    """Returns (passed, null_rate). Fails if null_rate >= threshold."""
    null_rate = series.isna().mean()
    return null_rate < NULL_RATE_THRESHOLD, round(null_rate, 4)


def _check_variance(series: pd.Series) -> tuple[bool, int, bool]:
    """
    Returns (passed, n_unique, is_near_constant).
    Fails if the column has <= NEAR_CONSTANT_THRESHOLD unique non-null
    values — i.e. it carries (almost) no information regardless of
    how complete it is.
    """
    n_unique = series.dropna().nunique()
    is_near_constant = n_unique <= NEAR_CONSTANT_THRESHOLD
    return not is_near_constant, n_unique, is_near_constant


def _check_leakage(
    series: pd.Series, target: pd.Series
) -> tuple[bool, float | None, bool, bool]:
    """
    Returns (passed, correlation, leakage_flag, leakage_warning).

    Only meaningful for numeric (or numeric-coercible) columns —
    non-numeric columns return (True, None, False, False) since a
    correlation-based leakage check doesn't directly apply to raw
    categorical text without encoding (encoding-aware leakage
    detection is intentionally out of scope for this first build —
    see module docstring future-work note).

    This is the check that would have caught the original Healthcare
    BMI incident (BMI was perfectly correlated with Churn) BEFORE a
    model was trained on it, rather than discovering it only after
    seeing a suspicious 100% accuracy score.
    """
    numeric_series = pd.to_numeric(series, errors='coerce')
    numeric_target  = pd.to_numeric(target, errors='coerce')

    valid_mask = numeric_series.notna() & numeric_target.notna()
    if valid_mask.sum() < 10:
        # Not enough overlapping numeric data to compute a meaningful
        # correlation — don't flag, don't claim a number either.
        return True, None, False, False

    try:
        corr = numeric_series[valid_mask].corr(numeric_target[valid_mask])
    except Exception:
        return True, None, False, False

    if corr is None or np.isnan(corr):
        return True, None, False, False

    abs_corr = abs(corr)
    leakage_flag    = abs_corr >= LEAKAGE_CORRELATION_HIGH
    leakage_warning = (not leakage_flag) and abs_corr >= LEAKAGE_CORRELATION_WARN
    passed = not leakage_flag

    return passed, round(float(corr), 4), leakage_flag, leakage_warning


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

def run_quality_gate(
    df: pd.DataFrame,
    target_col: str | None = None,
) -> dict:
    """
    Run the full Information Quality Engine over every column in df.

    Parameters
    ----------
    df : pd.DataFrame
        Raw or canonical input data. Works the same regardless of
        whether columns have been through schema_resolution.py yet —
        quality is a property of the data values, not the column
        names.
    target_col : str, optional
        If provided and present in df, every other column is checked
        for correlation-based leakage against it. If omitted (e.g.
        scoring a genuinely unlabeled new-customer file), the leakage
        check is skipped entirely and quality results report null
        correlation rather than a false pass/fail.

    Returns
    -------
    dict with keys:
        'column_results'   : list[ColumnQualityResult] — one per column
        'failed_columns'   : list[str] — columns that failed ANY check
        'leakage_flagged'  : list[str] — columns flagged as likely leaked
        'leakage_warned'   : list[str] — columns in the 0.80–0.95 warn band
        'leakage_detected' : bool — True if leakage_flagged is non-empty
        'overall_passed'   : bool — True only if no column has a hard
                              leakage flag (null-rate/variance failures
                              alone do not block overall_passed — those
                              are expected and already handled by
                              coverage scoring; leakage is the one
                              failure mode serious enough to block)
    """
    has_target = target_col is not None and target_col in df.columns
    target_series = df[target_col] if has_target else None

    results: list[ColumnQualityResult] = []

    for col in df.columns:
        if has_target and col == target_col:
            continue  # never quality-check the target against itself

        series = df[col]
        reasons: list[str] = []

        null_passed, null_rate = _check_null_rate(series)
        if not null_passed:
            reasons.append(f"mostly null ({null_rate*100:.0f}%)")

        var_passed, n_unique, is_near_constant = _check_variance(series)
        if not var_passed:
            reasons.append(f"constant / near-constant ({n_unique} unique value(s))")

        if has_target:
            leak_passed, corr, leak_flag, leak_warn = _check_leakage(
                series, target_series
            )
            if leak_flag:
                reasons.append(
                    f"SUSPECTED TARGET LEAKAGE — correlation with "
                    f"'{target_col}' is {corr} (>= {LEAKAGE_CORRELATION_HIGH})"
                )
            elif leak_warn:
                reasons.append(
                    f"elevated correlation with target ({corr}) — "
                    f"not flagged as leakage but worth manual review"
                )
        else:
            leak_passed, corr, leak_flag, leak_warn = True, None, False, False

        passed = null_passed and var_passed and leak_passed

        results.append(ColumnQualityResult(
            column=col,
            passed=passed,
            null_rate=null_rate,
            n_unique=n_unique,
            is_near_constant=is_near_constant,
            target_correlation=corr,
            leakage_flag=leak_flag,
            leakage_warning=leak_warn,
            reasons=reasons,
        ))

    failed_columns  = [r.column for r in results if not r.passed]
    leakage_flagged = [r.column for r in results if r.leakage_flag]
    leakage_warned  = [r.column for r in results if r.leakage_warning]

    return {
        'column_results'  : results,
        'failed_columns'  : failed_columns,
        'leakage_flagged' : leakage_flagged,
        'leakage_warned'  : leakage_warned,
        'leakage_detected': len(leakage_flagged) > 0,
        'overall_passed'  : len(leakage_flagged) == 0,
    }


def print_quality_report(quality_result: dict, sector: str = "") -> None:
    """
    Human-readable quality report, printed in the same visual style
    as coverage.py's _print_coverage_report() for consistency in the
    CLI output. Called from the CLI's --report flag alongside the
    coverage report, not instead of it.
    """
    sep = '─' * 60
    print(f"\n{sep}")
    title = f"  DATA QUALITY REPORT" + (f"  [{sector.upper()}]" if sector else "")
    print(title)
    print(sep)

    if quality_result['leakage_detected']:
        print(f"  ⚠ TARGET LEAKAGE DETECTED")
        for col in quality_result['leakage_flagged']:
            r = next(c for c in quality_result['column_results'] if c.column == col)
            print(f"    [LEAKAGE] {col}  (correlation={r.target_correlation})")
        print(
            f"\n  Recommendation: exclude these columns before training. "
            f"A column this strongly correlated with the target almost "
            f"always indicates the label leaked into the features "
            f"(e.g. the feature was computed FROM the outcome) rather "
            f"than genuinely predicting it."
        )
    else:
        print(f"  ✔ No target leakage detected.")

    if quality_result['leakage_warned']:
        print(f"\n  Elevated correlation (review recommended, not blocking):")
        for col in quality_result['leakage_warned']:
            r = next(c for c in quality_result['column_results'] if c.column == col)
            print(f"    [{r.target_correlation}]  {col}")

    failed_non_leakage = [
        c for c in quality_result['failed_columns']
        if c not in quality_result['leakage_flagged']
    ]
    if failed_non_leakage:
        print(f"\n  Columns failing null-rate or variance checks:")
        for col in failed_non_leakage:
            r = next(c for c in quality_result['column_results'] if c.column == col)
            print(f"    {col}: {'; '.join(r.reasons)}")

    print(sep)
