"""
universal_churn/cli.py
Command-line interface for the universal churn prediction framework.

Routing note
------------
The auto-mode branch previously branched directly on
compute_coverage_score()'s 'Refused'/'Full'/'Fallback' values. It now
computes coverage + quality, calls routing.route() exactly once, and
dispatches purely on RoutingDecision.selected_model — the CLI makes no
routing decisions of its own, matching sector_pipeline.py and
universal_pipeline.py.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from .config import SECTOR_CONFIG
from .preprocessing import detect_sector
from .reporting import _maybe_emit_report
from .prediction_explanation_report import (
    build_and_attach_explanations, print_prediction_explanation_report,
    print_execution_summary,
)
from .coverage import compute_coverage_score
from .quality_gate import run_quality_gate
from .routing import route, ModelType
from .sector_pipeline import SectorPipeline
from .universal_pipeline import train_universal_model, predict_universal
from .feature_engineering import build_canonical_dataframe


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build and return the parsed CLI namespace."""
    parser = argparse.ArgumentParser(
        description="Universal schema-agnostic churn predictor.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        '--mode',
        choices=[
            'train_sector', 'train_universal', 'sector', 'universal',
            'auto', 'train_all', 'list_heads',
        ],
        default='train_all',
    )
    parser.add_argument('--sector', type=str, default=None)
    parser.add_argument('--input', type=str, default=None)
    parser.add_argument('--output', type=str,
                        default='outputs/results/universal_predictions.csv')
    parser.add_argument('--tune', type=str, default=None, choices=['f1', 'recall'])
    parser.add_argument('--explain', action='store_true')
    parser.add_argument('--explain-output', type=str, default=None)
    parser.add_argument('--report', action='store_true')
    parser.add_argument('--report-output', type=str, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = parse_args(argv)

    if args.mode == 'train_all':
        print("\nTraining all sector pipelines...")
        for sector_name in SECTOR_CONFIG:
            try:
                SectorPipeline(sector_name, tune_metric=args.tune).fit()
            except FileNotFoundError as exc:
                print(f"  Skipping {sector_name}: {exc}")
        train_universal_model(tune_metric=args.tune)

    elif args.mode == 'train_sector':
        if not args.sector:
            raise ValueError("--sector is required for train_sector mode.")
        SectorPipeline(args.sector, tune_metric=args.tune).fit()

    elif args.mode == 'train_universal':
        train_universal_model(tune_metric=args.tune)

    elif args.mode == 'sector':
        # Routing decision (Green/Yellow → sector model w/ optional
        # warning, Red → refused, leakage → refused) is made entirely
        # inside SectorPipeline.predict() via routing.route(). The CLI
        # only loads the pipeline and surfaces whatever it returns.
        if not args.input:
            raise ValueError("--input is required for sector mode.")
        sector = args.sector
        if not sector:
            probe_df = pd.read_csv(args.input)
            sector = detect_sector(probe_df)
            print(f"  Auto-detected sector: {sector}")
        pipeline = SectorPipeline(sector).load()
        results = pipeline.predict(
            args.input, explain=args.explain,
            explain_output=args.explain_output, _prediction_mode='Sector')
        # Prediction Explanation Layer (Version 7, Chunk 5) — additive,
        # best-effort, never blocks prediction. See prediction_explanation.py
        # for the non-interference guarantee.
        probe_for_explanation = pd.read_csv(args.input)
        results = build_and_attach_explanations(results, probe_for_explanation, sector)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        routing_decision_obj = results.attrs.get('routing_decision')
        routing_decision_text = (
            routing_decision_obj.routing_reason if routing_decision_obj is not None
            else "User explicitly requested the sector-specific model."
        )
        _maybe_emit_report(
            results, sector,
            routing_decision=routing_decision_text,
            args=args)
        if getattr(args, 'report', False):
            explanation_report = results.attrs.get('prediction_explanation')
            if explanation_report is not None:
                print_prediction_explanation_report(explanation_report)
                print_execution_summary(explanation_report, results.attrs.get('coverage'))

    elif args.mode == 'universal':
        # Routing decision (quality gate / leakage check) is made
        # entirely inside predict_universal() via routing.route() when
        # called as the CLI entry point (no _precomputed_coverage).
        if not args.input:
            raise ValueError("--input is required for universal mode.")
        probe_df = pd.read_csv(args.input)
        sector_for_report = args.sector or detect_sector(probe_df)
        results = predict_universal(
            args.input, force_sector=args.sector,
            explain=args.explain, explain_output=args.explain_output,
            _prediction_mode='Universal')
        # Prediction Explanation Layer (Version 7, Chunk 5) — additive,
        # best-effort, never blocks prediction. See prediction_explanation.py
        # for the non-interference guarantee.
        probe_for_explanation = pd.read_csv(args.input)
        results = build_and_attach_explanations(
            results, probe_for_explanation, sector_for_report)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        routing_decision_obj = results.attrs.get('routing_decision')
        routing_decision_text = (
            routing_decision_obj.routing_reason if routing_decision_obj is not None
            else "User explicitly requested the universal model."
        )
        _maybe_emit_report(
            results, sector_for_report,
            routing_decision=routing_decision_text,
            args=args)
        if getattr(args, 'report', False):
            explanation_report = results.attrs.get('prediction_explanation')
            if explanation_report is not None:
                print_prediction_explanation_report(explanation_report)
                print_execution_summary(explanation_report, results.attrs.get('coverage'))

    elif args.mode == 'auto':
        # Centralized routing: compute coverage + quality, call
        # routing.route() exactly once, then dispatch purely on
        # RoutingDecision.selected_model. The CLI makes no routing
        # decisions of its own — it only executes what route() returns.
        if not args.input:
            raise ValueError("--input is required for auto mode.")
        probe_df = pd.read_csv(args.input)
        sector = args.sector or detect_sector(probe_df)
        print(f"  Auto mode — detected sector: {sector.upper()}")

        canonical_df, _resolutions, _manifest = build_canonical_dataframe(probe_df)
        coverage = compute_coverage_score(
            df_input=canonical_df, sector=sector, mode='auto', raw_df=probe_df)
        quality = run_quality_gate(
            probe_df, target_col=SECTOR_CONFIG[sector]['target_col'])

        decision = route(mode='auto', coverage=coverage, quality=quality, sector=sector)
        print(f"  Routing decision: {decision.selected_model.value} "
              f"— {decision.routing_reason}")

        if decision.selected_model == ModelType.CRITICAL_UNRELIABLE:
            raise ValueError(
                f"Auto mode — prediction refused for sector '{sector}': "
                f"{decision.routing_reason}"
            )

        if decision.selected_model == ModelType.FULL_SECTOR_MODEL:
            pipeline = SectorPipeline(sector).load()
            results = pipeline.predict(
                args.input, explain=args.explain,
                explain_output=args.explain_output, _prediction_mode='Auto')

        elif decision.selected_model == ModelType.UNIVERSAL_MODEL:
            results = predict_universal(
                args.input, force_sector=sector,
                explain=args.explain, explain_output=args.explain_output,
                _prediction_mode='Auto', _precomputed_coverage=coverage)
            for k, v in decision.report_fields().items():
                results[k] = v
            results.attrs['coverage'] = coverage
            results.attrs['quality'] = quality
            results.attrs['routing_decision'] = decision

        elif decision.selected_model == ModelType.CORE_MODEL:
            # Future-readiness hook — route() does not currently return
            # CORE_MODEL (see routing.py auto-mode Yellow branch comment),
            # but the dispatch path is wired so enabling it later requires
            # no CLI changes, only a CoreModelPipeline implementation.
            raise NotImplementedError(
                "Routing selected CORE_MODEL, but no core model pipeline "
                "is implemented yet. This is a future-readiness hook."
            )
        else:
            raise RuntimeError(
                f"Unhandled RoutingDecision.selected_model: {decision.selected_model}"
            )

        # Prediction Explanation Layer (Version 7, Chunk 5) — additive,
        # best-effort, never blocks prediction. See prediction_explanation.py
        # for the non-interference guarantee.
        probe_for_explanation = pd.read_csv(args.input)
        results = build_and_attach_explanations(results, probe_for_explanation, sector)

        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        _maybe_emit_report(results, sector,
                           routing_decision=decision.routing_reason, args=args)
        if getattr(args, 'report', False):
            explanation_report = results.attrs.get('prediction_explanation')
            if explanation_report is not None:
                print_prediction_explanation_report(explanation_report)
                print_execution_summary(explanation_report, results.attrs.get('coverage'))

    elif args.mode == 'list_heads':
        print("\nMulti-head model architecture:")
        print(f"{'Sector': <12} {'Model file': <55} {'Trained?'}")
        print("-" * 85)
        for sector_name, cfg in SECTOR_CONFIG.items():
            model_file = cfg['model_path']
            trained = "Yes" if Path(model_file).exists() else "No"
            print(f"{sector_name: <12} {model_file: <55} {trained}")
