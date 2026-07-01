"""
universal_churn/coverage.py
────────────────────────────
Weighted feature coverage scoring and feature recovery.

Phase 5 note — coverage.py is a pure MEASUREMENT engine
--------------------------------------------------------
This module answers exactly one question: "how much of the expected
feature schema is actually present, populated, and usable in this
input?" It never decides whether a prediction is accepted, refused,
or which model runs — that is routing.py's job, and routing.py's
alone (see routing.route()). coverage.py does not import routing.py
and has no notion of ModelType/RoutingDecision.

Coverage bands (measurement only — NOT a routing decision)
────────────────────────────────────────────────────────────
Green  ≥ 85%  →  feature schema is well-populated
Yellow 60–85% →  feature schema is partially populated
Red    < 60%  →  feature schema is sparse

What a band like 'Red' MEANS for prediction (full sector model vs.
universal fallback vs. refusal) is entirely determined downstream by
routing.route(), which also weighs Concept Confidence and the Quality
Gate before deciding. A 'Red' coverage score on its own no longer
implies refusal — see routing.py's _red_coverage_decision().
"""
from __future__ import annotations

import pandas as pd

from .config import SECTOR_FEATURE_WEIGHTS
from .concept_confidence import compute_concept_confidence, print_concept_confidence_report


# ── Feature recovery rules ────────────────────────────────────────
# (target_feature, [source_columns_needed], derivation_fn)
_DERIVATION_RULES: list[tuple[str, list[str], object]] = [
    (
        'Tenure_Months', ['Policy_Start_Date'],
        lambda df: (
            (pd.Timestamp.now() - pd.to_datetime(df['Policy_Start_Date'], errors='coerce'))
            .dt.days / 30.44
        ).round(1),
    ),
    (
        'Age', ['Date_of_Birth'],
        lambda df: (
            (pd.Timestamp.now() - pd.to_datetime(df['Date_of_Birth'], errors='coerce'))
            .dt.days / 365.25
        ).round(0),
    ),
    (
        'Days_Since_Last_Visit', ['Last_Visit_Date'],
        lambda df: (
            (pd.Timestamp.now() - pd.to_datetime(df['Last_Visit_Date'], errors='coerce'))
            .dt.days
        ).round(0),
    ),
    (
        'DaySinceLastOrder', ['Last_Order_Date'],
        lambda df: (
            (pd.Timestamp.now() - pd.to_datetime(df['Last_Order_Date'], errors='coerce'))
            .dt.days
        ).round(0),
    ),
    (
        'MonthlyCharges', ['AnnualPremium'],
        lambda df: (df['AnnualPremium'] / 12).round(2),
    ),
    (
        'Avg_Out_Of_Pocket_Cost', ['AnnualPremium'],
        lambda df: (df['AnnualPremium'] / 12).round(2),
    ),
    (
        'Visits_Last_Year', ['Visit_History'],
        lambda df: pd.to_numeric(df['Visit_History'], errors='coerce').fillna(0),
    ),
]


def _attempt_feature_recovery(df: pd.DataFrame, sector: str) -> pd.DataFrame | None:
    """
    Try to derive missing features from known proxy columns before
    routing to the universal model fallback.
    Returns an enriched copy of df if at least one feature was recovered,
    or None if nothing could be derived.
    """
    df_cols_lower = {c.lower().replace('_', ''): c for c in df.columns}
    recovered     = df.copy()
    any_recovered = False

    for target_feat, sources, derive_fn in _DERIVATION_RULES:
        target_lower = target_feat.lower().replace('_', '')
        if target_lower in df_cols_lower:
            continue

        src_map = {}
        for src in sources:
            src_lower = src.lower().replace('_', '')
            if src_lower in df_cols_lower:
                src_map[src] = df_cols_lower[src_lower]
            else:
                src_map = {}
                break
        if not src_map:
            continue

        tmp = recovered.rename(columns={v: k for k, v in src_map.items()})
        try:
            recovered[target_feat] = derive_fn(tmp).values
            print(f"  Recovered '{target_feat}' from {sources}")
            any_recovered = True
        except Exception as exc:
            print(f"  Recovery of '{target_feat}' failed: {exc}")

    return recovered if any_recovered else None


# Public alias — sector_pipeline.py and other callers outside this module
# import the public name; the leading-underscore name remains for any
# internal call sites already using it.
attempt_feature_recovery = _attempt_feature_recovery


def compute_coverage_score(
    df_input: pd.DataFrame,
    sector: str,
    mode: str = 'sector',
    green_threshold: float = 0.85,
    yellow_threshold: float = 0.60,
    _suppress_print: bool = False,
    recovered_features: list[str] | None = None,
) -> dict:
    """
    Compute weighted feature coverage score for the input CSV.

    Coverage Score = Σ(weight_i × quality_i) / Σ(weight_i)

    quality_i = 1  if column is present, <95% null, and non-constant
    quality_i = 0  otherwise

    Parameters
    ----------
    recovered_features : list[str], optional
        Names of features that an upstream caller (e.g. sector_pipeline.py,
        via attempt_feature_recovery()) derived from proxy columns BEFORE
        this coverage score was computed. Purely informational — passing
        this does not change the score, it is only echoed back in the
        return dict so callers/reports can show which features were
        reconstructed rather than natively present. Defaults to an empty
        list when not supplied (fully backward compatible — omitting this
        argument changes nothing about existing behaviour).

    Returns a dict with keys:
        coverage_score      float   — the measurement itself
        status               'Green' | 'Yellow' | 'Red'   — coverage BAND
                              (a measurement label, not a routing decision)
        coverage_band        same value as `status`, exposed under the
                              forward-looking name used by routing.py /
                              reporting.py's diagnostics (item 5 of the
                              Phase 5 spec). Prefer this key in new code.
        prediction_mode      DEPRECATED — 'Full' | 'Fallback' | 'Refused'.
                              This is a decision-shaped label left over
                              from before Phase 5 and is retained ONLY so
                              older callers reading this exact key don't
                              break. coverage.py does not act on it and
                              routing.py does not read it — routing.route()
                              derives its own decision from `status`,
                              Concept Confidence, and the Quality Gate.
                              Do not add new reads of this key; use
                              `coverage_band` and let routing.py decide.
        missing_critical     list  (weight ≥ 4 features that failed)
        missing_high_impact  list  (weight = 3 features that failed)
        missing_all          list  (all features that failed)
        recovered_features   list  (echoed back from the `recovered_features`
                              argument — measurement context only)
        detail               list[dict]  per-feature breakdown
    """
    weights      = SECTOR_FEATURE_WEIGHTS.get(sector, {c: 1 for c in df_input.columns})
    total_weight = sum(weights.values())

    def _strip(s: str) -> str:
        return s.lower().replace('_', '').replace(' ', '')

    stripped_to_original = {_strip(c): c for c in df_input.columns}

    detail           = []
    earned_weight    = 0.0
    missing_all      = []
    missing_critical = []

    for feat, weight in weights.items():
        orig_col = stripped_to_original.get(_strip(feat))

        if orig_col is None:
            quality, reason = 0, 'absent'
        else:
            col      = df_input[orig_col]
            pct_null = col.isna().mean()
            numeric  = pd.to_numeric(col, errors='coerce')
            n_unique = numeric.dropna().nunique()

            if pct_null >= 0.95:
                quality, reason = 0, f'mostly null ({pct_null*100:.0f}%)'
            elif n_unique <= 1:
                quality, reason = 0, 'constant (no variance)'
            else:
                quality, reason = 1, 'OK'

        earned_weight += weight * quality
        detail.append({'feature': feat, 'weight': weight,
                       'quality': quality, 'reason': reason})
        if quality == 0:
            missing_all.append(feat)
            if weight >= 4:
                missing_critical.append(feat)

    coverage_score = earned_weight / total_weight if total_weight > 0 else 0.0

    if coverage_score >= green_threshold:
        status, prediction_mode = 'Green', 'Full'
    elif coverage_score >= yellow_threshold:
        status, prediction_mode = 'Yellow', 'Fallback'
    else:
        status, prediction_mode = 'Red', 'Refused'

    missing_high_impact = [
        f for f in missing_all
        if f not in missing_critical and weights.get(f, 0) >= 3
    ]

    # ── Concept Confidence (Phase 4, additive) ──────────────────────
    # Runs independently of the feature-weight scoring above and does
    # NOT change coverage_score/status/prediction_mode in any way — it
    # is attached to the return dict alongside them, per the Schema
    # Intelligence Layer spec ("Add concept confidence alongside it.
    # Do not replace existing coverage logic."). routing.py's
    # CoverageResult.from_coverage_dict() reads this key when present
    # and falls back to None if it's ever missing (e.g. older cached
    # coverage dicts), so this is fully backward compatible.
    try:
        concept_confidence_report = compute_concept_confidence(df_input, sector)
        concept_confidence = concept_confidence_report.to_dict()
    except Exception as exc:
        # Never let a concept-confidence failure block coverage scoring
        # or prediction — degrade to "unknown" instead.
        concept_confidence = {
            'sector': sector, 'per_concept': {}, 'overall_confidence': 0.0,
            'reconstructable_concepts': 0, 'total_concepts': 0,
            'concepts_reconstructable': False,
            'error': f"concept confidence computation failed: {exc}",
        }

    if not _suppress_print:
        _print_coverage_report(
            coverage_score, status, prediction_mode, sector, mode,
            weights, detail, missing_critical, missing_high_impact, missing_all,
            concept_confidence, recovered_features,
        )
        print_concept_confidence_report(concept_confidence)

    return {
        'coverage_score'      : round(coverage_score, 4),
        'status'              : status,
        'coverage_band'       : status,                 # forward-looking alias — see docstring
        'prediction_mode'     : prediction_mode,         # DEPRECATED — measurement only, not a decision
        'missing_critical'    : missing_critical,
        'missing_high_impact' : missing_high_impact,
        'missing_all'         : missing_all,
        'recovered_features'  : list(recovered_features) if recovered_features else [],
        'detail'              : detail,
        'concept_confidence'  : concept_confidence,
    }


def _print_coverage_report(
    coverage_score, status, prediction_mode, sector, mode,
    weights, detail, missing_critical, missing_high_impact, missing_all,
    concept_confidence=None, recovered_features=None,
) -> None:
    sep   = '─' * 60
    icons = {'Green': '✔', 'Yellow': '△', 'Red': '✖'}
    print(f"\n{sep}")
    print(f"  COVERAGE SCORE REPORT  [{mode.upper()} / {sector.upper()}]")
    print(sep)
    print(f"  Weighted coverage score : {coverage_score*100:.1f}%")
    print(f"  Coverage band           : {icons[status]} {status}  (measurement only — "
          f"no routing decision is made here)")
    print(f"  Legacy band label       : {prediction_mode}  (deprecated, decision-shaped "
          f"field kept only for backward compatibility — ignored by routing.py)")

    if missing_critical:
        print(f"\n  Missing critical features (weight ≥ 4):")
        for f in missing_critical:
            r = next(d['reason'] for d in detail if d['feature'] == f)
            print(f"    [{weights[f]}]  {f}  ({r})")

    if missing_high_impact:
        print(f"\n  Missing high-impact features (weight = 3):")
        for f in missing_high_impact:
            r = next(d['reason'] for d in detail if d['feature'] == f)
            print(f"    [{weights[f]}]  {f}  ({r})")

    low_missing = [f for f in missing_all
                   if f not in missing_critical and f not in missing_high_impact]
    if low_missing:
        print(f"\n  Lower-weight features missing or unusable:")
        for f in low_missing:
            r = next(d['reason'] for d in detail if d['feature'] == f)
            print(f"    [{weights[f]}]  {f}  ({r})")

    if recovered_features:
        print(f"\n  Recovered features (derived from proxy columns upstream):")
        for f in recovered_features:
            print(f"    ~ {f}")

    # ── Phase 4/5 (v5.2): informational only, no decisions here ────
    # coverage.py measures FEATURE availability and stops there. It
    # does not decide which model runs or whether a prediction is
    # refused — that is routing.py's job (routing.py combines this
    # coverage_score with Concept Confidence and the Quality Gate).
    # This module cross-references reconstructed concepts for context
    # only; it does not merge the two metrics into one number.
    print(f"\n  This score measures FEATURE availability only. It does not, by "
          f"itself, determine which model runs or whether a prediction is "
          f"made — see the Concept Confidence report below and the "
          f"Routing Decision for that.")
    if concept_confidence and concept_confidence.get('per_concept'):
        reconstructed = [
            name for name, e in concept_confidence['per_concept'].items()
            if e.get('reconstructable')
        ]
        print(
            f"  Cross-reference — business concepts reconstructed for this "
            f"input regardless of feature coverage: "
            f"{reconstructed if reconstructed else 'None'}"
        )

    print(sep)
