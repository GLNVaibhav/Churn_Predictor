"""
universal_churn/reporting.py
─────────────────────────────
Prediction quality reporting and metadata attachment.
No ML computation here — only formatting and serialisation.

Phase 5 role — reporting.py EXPLAINS, it does not decide
------------------------------------------------------------
    coverage.py    reports MEASUREMENTS  (is the feature there? is it usable?)
    routing.py     makes the DECISION    (which model runs, accept/reject)
    reporting.py   EXPLAINS the decision (renders both, plus the verdict,
                   for a human on the terminal and for machine-readable
                   diagnostics in saved CSV/JSON output)

reporting.py never computes a coverage score, a quality band, or a
routing decision itself — it only formats and attaches values that
coverage.py / quality_gate.py / concept_confidence.py / routing.py
already produced. print_full_diagnostic_report() below is the single
place that assembles the full terminal narrative, in this order:
Coverage Report -> Concept Confidence Report -> Quality Report ->
Routing Decision -> Prediction Reliability -> Prediction Output.
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
from .quality_gate import print_quality_report
from .routing import RoutingDecision


def print_routing_decision(decision: RoutingDecision) -> None:
    """
    Human-readable Routing Decision report, in the same visual style
    as coverage.py / quality_gate.py / concept_confidence.py's report
    printers. This is the dedicated "Routing Decision" + "Prediction
    Reliability" section of the full diagnostic report (see
    print_full_diagnostic_report() below).

    Relocated here from routing.py per Phase 5 item 3: routing.py
    produces structured RoutingDecision objects only; reporting.py
    owns every terminal-facing explanation, including this one.
    """
    sep = '─' * 60
    print(f"\n{sep}")
    print(f"  ROUTING DECISION")
    print(sep)
    print(f"  Verdict                 : {decision.acceptance_banner}")
    print(f"  Selected model          : {decision.selected_model.value}")
    print(f"  Model artifact          : {decision.model_artifact}")
    print(f"  Coverage band           : {decision.coverage_band}  "
          f"({decision.coverage_score*100:.1f}%)")
    print(f"  Quality status          : {decision.quality_status}  "
          f"({decision.quality_score*100:.1f}%)")
    print(f"  Concept confidence      : "
          f"{f'{decision.concept_confidence*100:.1f}%' if decision.concept_confidence is not None else 'N/A'}")
    print(f"  Prediction reliability  : {decision.reliability.value}")
    print(f"\n  Reason:")
    print(f"    {decision.routing_reason}")
    if decision.warnings:
        print(f"\n  Warnings:")
        for w in decision.warnings:
            print(f"    ⚠ {w}")
    print(sep)


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


def attach_routing_diagnostics(
    results: pd.DataFrame,
    decision: RoutingDecision,
) -> pd.DataFrame:
    """
    Write the routing decision's machine-readable fields onto every row
    of `results`, so they persist into saved CSV/JSON output (Phase 5,
    item 5): Selected_Model, Routing_Reason, Coverage_Score,
    Coverage_Band, Quality_Score, Quality_Status, Prediction_Reliability,
    Concept_Confidence, Routing_Warnings, Model_Artifact, and version/
    timestamp columns. Safe to call multiple times — only adds/overwrites
    its own columns, and does not touch Prediction_Confidence or the
    per-sector model-version columns owned by attach_common_metadata().
    """
    for k, v in decision.report_fields().items():
        results[k] = v
    return results


def generate_prediction_quality_report(
    results: pd.DataFrame,
    coverage: dict | None,
    sector: str,
    explain_summary: dict | None = None,
    routing_decision: "str | RoutingDecision | None" = None,
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

        # Phase 6 diagnostics — Concept Confidence (concept_confidence.py,
        # attached to the coverage dict by coverage.py). Optional key:
        # older/cached coverage dicts without it are simply skipped.
        concept_conf = coverage.get('concept_confidence')
        if concept_conf:
            lines.append("")
            lines.append(f"Concept Confidence (overall) : {concept_conf['overall_confidence']*100:.1f}%")
            lines.append(
                f"Reconstructable Concepts     : "
                f"{concept_conf['reconstructable_concepts']}/{concept_conf['total_concepts']}"
            )
            for name, entry in concept_conf.get('per_concept', {}).items():
                mark = '✔' if entry['reconstructable'] else '✖'
                field = f" <- {entry['canonical_field']}" if entry.get('canonical_field') else ""
                lines.append(f"    {mark} {name:<22} {entry['confidence']*100:5.1f}%{field}")

    if isinstance(routing_decision, RoutingDecision):
        d = routing_decision
        lines += [
            "",
            "Routing Decision:",
            f"    Verdict            : {d.acceptance_banner}",
            f"    Selected model     : {d.selected_model.value}",
            f"    Model artifact     : {d.model_artifact}",
            f"    Coverage band      : {d.coverage_band}",
            f"    Quality status     : {d.quality_status}",
            f"    Reason             : {d.routing_reason}",
        ]
        if d.warnings:
            lines.append("    Warnings           : " + "; ".join(d.warnings))
        lines += [
            "",
            "Prediction Reliability:",
            f"    {d.reliability.value}",
        ]
    elif routing_decision:
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


def print_full_diagnostic_report(
    quality: dict | None,
    decision: RoutingDecision | None,
) -> None:
    """
    Terminal narrative for one prediction run, sections clearly
    separated per Phase 5 item 4:

        Coverage Report            -- printed by coverage.py itself
        Concept Confidence Report  -- printed by coverage.py itself
                                       (both already happen inside
                                       compute_coverage_score() unless
                                       _suppress_print=True was passed —
                                       reporting.py does not re-print
                                       them, to avoid duplicated output)
        Quality Report             -- printed here, via quality_gate.py
        Routing Decision           -- printed here, via routing.py
        Prediction Reliability     -- part of the Routing Decision
                                       section above (routing.py owns
                                       both, since reliability is
                                       derived alongside the decision)

    Either argument may be None (e.g. quality wasn't run, or routing
    wasn't reached because of an earlier hard failure) — sections are
    skipped rather than erroring.
    """
    if quality is not None:
        print_quality_report(quality)
    if decision is not None:
        print_routing_decision(decision)


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
    quality         = results.attrs.get('quality')
    explain_summary = results.attrs.get('explain_summary')

    # Prefer the typed RoutingDecision stashed in .attrs (set by the
    # auto-mode routing path) over the plain routing_reason string
    # callers pass positionally — the object carries reliability,
    # coverage/quality bands, and warnings that the string alone can't.
    decision_obj = results.attrs.get('routing_decision')
    routing_decision_for_report = decision_obj if decision_obj is not None else routing_decision

    # Quality/Routing sections (Coverage + Concept Confidence were
    # already printed by coverage.py at scoring time).
    print_full_diagnostic_report(quality, decision_obj)

    report_text = generate_prediction_quality_report(
        results, coverage, sector,
        explain_summary=explain_summary,
        routing_decision=routing_decision_for_report,
    )
    print("\n" + report_text)
    if args.report_output:
        fmt = 'json' if args.report_output.lower().endswith('.json') else 'txt'
        extra_json_fields = (
            {'diagnostics': decision_obj.to_diagnostics_dict()} if decision_obj is not None else None
        )
        save_prediction_report(
            report_text, args.report_output, fmt=fmt,
            extra_json_fields=extra_json_fields,
        )
