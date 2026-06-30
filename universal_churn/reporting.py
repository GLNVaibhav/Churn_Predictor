"""
universal_churn/reporting.py
─────────────────────────────
Prediction quality reporting and metadata attachment.
No ML computation here — only formatting and serialisation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import (
    PIPELINE_VERSION, SECTOR_MODEL_VERSION, UNIVERSAL_MODEL_VERSION,
    NORMALIZATION_VERSION, COVERAGE_ALGORITHM_VERSION,
)
from .utils import _utc_timestamp, prediction_confidence_label, coverage_confidence_label


def attach_common_metadata(
    results: pd.DataFrame,
    coverage: dict | None,
    prediction_model_label: str,
) -> pd.DataFrame:
    """
    Add confidence indicators and provenance columns to every prediction
    result, regardless of mode. Safe to call multiple times — only
    adds/overwrites its own columns.
    """
    results['Prediction_Confidence'] = results['Churn_Probability'].apply(
        prediction_confidence_label
    )
    if coverage is not None:
        results['Coverage_Confidence'] = coverage_confidence_label(
            coverage['coverage_score']
        )

    results['Prediction_Timestamp']       = _utc_timestamp()
    results['Pipeline_Version']           = PIPELINE_VERSION
    results['Sector_Model_Version']       = (
        SECTOR_MODEL_VERSION if 'Sector' in prediction_model_label else 'N/A'
    )
    results['Universal_Model_Version']    = (
        UNIVERSAL_MODEL_VERSION if 'Universal' in prediction_model_label else 'N/A'
    )
    results['Normalization_Version']      = NORMALIZATION_VERSION
    results['Coverage_Algorithm_Version'] = COVERAGE_ALGORITHM_VERSION
    return results


def generate_prediction_quality_report(
    results: pd.DataFrame,
    coverage: dict | None,
    sector: str,
    explain_summary: dict | None = None,
    routing_decision: str | None = None,
) -> str:
    """
    Build a concise human-readable inference summary.
    All data comes from `results` and `coverage` — no new ML computation.
    """
    sep   = "=" * 56
    lines = [sep, "PREDICTION QUALITY REPORT", sep, ""]

    lines.append(f"Sector                  : {sector.capitalize()}")
    lines.append(f"Prediction Model        : {results['Prediction_Model'].iloc[0]}")
    lines.append(f"Prediction Mode         : {results['Prediction_Mode'].iloc[0]}")

    if coverage is not None:
        lines.append(f"Coverage Score          : {coverage['coverage_score']*100:.1f}%")
        lines.append(f"Coverage Status         : {coverage['status']}")
        lines.append(f"Coverage Confidence     : {coverage_confidence_label(coverage['coverage_score'])}")

        missing_crit = coverage.get('missing_critical', [])
        missing_hi   = coverage.get('missing_high_impact', [])
        lines.append("")
        lines.append("Missing Critical Features:")
        lines.append("    None" if not missing_crit
                     else "\n".join(f"    - {f}" for f in missing_crit))
        lines.append("Missing High-Impact Features:")
        lines.append("    None" if not missing_hi
                     else "\n".join(f"    - {f}" for f in missing_hi))

    if routing_decision:
        lines += ["", "Routing Decision:", f"    {routing_decision}"]

    n_rows = len(results)
    n_churn = (results['Predicted_Churn'] == 'Yes').sum()
    lines += [
        "",
        f"Rows predicted          : {n_rows}",
        f"Predicted churners      : {n_churn} ({n_churn/n_rows*100:.1f}%)",
    ]

    if 'Risk_Level' in results.columns:
        dist = results['Risk_Level'].value_counts().to_dict()
        lines.append(f"Risk distribution       : {dist}")

    if explain_summary:
        lines += [
            "",
            "SHAP Summary (dataset-wide):",
            f"    Top factors increasing churn : {explain_summary.get('top_increasing', [])}",
            f"    Top factors decreasing churn : {explain_summary.get('top_decreasing', [])}",
        ]

    lines += [
        "",
        "Provenance:",
        f"    Pipeline Version            : {PIPELINE_VERSION}",
        f"    Sector Model Version        : {results['Sector_Model_Version'].iloc[0]}",
        f"    Universal Model Version     : {results['Universal_Model_Version'].iloc[0]}",
        f"    Normalization Version       : {NORMALIZATION_VERSION}",
        f"    Coverage Algorithm Version  : {COVERAGE_ALGORITHM_VERSION}",
        sep,
    ]

    return "\n".join(lines)


def save_prediction_report(
    report_text: str,
    output_path: str,
    fmt: str = 'txt',
    extra_json_fields: dict | None = None,
) -> None:
    """Save the prediction quality report as .txt or .json."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if fmt == 'json':
        payload = {'report_text': report_text}
        if extra_json_fields:
            payload.update(extra_json_fields)
        with open(output_path, 'w') as f:
            json.dump(payload, f, indent=2, default=str)
    else:
        with open(output_path, 'w') as f:
            f.write(report_text)
    print(f"\nPrediction quality report saved: {output_path}")


def _maybe_emit_report(
    results: pd.DataFrame,
    sector: str,
    routing_decision: str | None,
    args,
) -> None:
    """
    Shared report-emission helper for the sector/universal/auto CLI
    branches. Reads coverage/explain_summary from the DataFrame's
    .attrs (set inside predict()/predict_universal()), so calling this
    requires no change to either function's return signature.
    Only prints/saves when --report or --report-output was passed.
    """
    if not (getattr(args, 'report', False) or getattr(args, 'report_output', None)):
        return
    coverage        = results.attrs.get('coverage')
    explain_summary = results.attrs.get('explain_summary')
    report_text = generate_prediction_quality_report(
        results, coverage, sector,
        explain_summary=explain_summary,
        routing_decision=routing_decision,
    )
    print("\n" + report_text)
    if args.report_output:
        fmt = 'json' if args.report_output.lower().endswith('.json') else 'txt'
        save_prediction_report(report_text, args.report_output, fmt=fmt)
