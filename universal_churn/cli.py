"""
universal_churn/cli.py
Command-line interface for the universal churn prediction framework.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from .config import SECTOR_CONFIG
from .preprocessing import detect_sector
from .reporting import _maybe_emit_report
from .coverage import compute_coverage_score
from .sector_pipeline import SectorPipeline
from .universal_pipeline import train_universal_model, predict_universal


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build and return the parsed CLI namespace."""
    parser = argparse.ArgumentParser(
        description="Universal schema-agnostic churn predictor.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    # FIX: removed leading space in ' train_sector'
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
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        _maybe_emit_report(
            results, sector,
            routing_decision="User explicitly requested the sector-specific model.",
            args=args)

    elif args.mode == 'universal':
        if not args.input:
            raise ValueError("--input is required for universal mode.")
        probe_df = pd.read_csv(args.input)
        sector_for_report = args.sector or detect_sector(probe_df)
        results = predict_universal(
            args.input, force_sector=args.sector,
            explain=args.explain, explain_output=args.explain_output,
            _prediction_mode='Universal')
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        _maybe_emit_report(
            results, sector_for_report,
            routing_decision="User explicitly requested the universal model.",
            args=args)

    elif args.mode == 'auto':
        if not args.input:
            raise ValueError("--input is required for auto mode.")
        probe_df = pd.read_csv(args.input)
        sector = args.sector or detect_sector(probe_df)
        print(f"  Auto mode — detected sector: {sector.upper()}")
        coverage = compute_coverage_score(
            df_input=probe_df, sector=sector, mode='auto')
        if coverage['prediction_mode'] == 'Refused':
            raise ValueError(
                f"Auto mode — prediction refused for sector '{sector}': "
                f"weighted coverage {coverage['coverage_score']*100:.1f}% < 60%.")
        elif coverage['prediction_mode'] == 'Full':
            routing_decision = "Coverage at or above threshold — using sector model."
            pipeline = SectorPipeline(sector).load()
            results = pipeline.predict(
                args.input, explain=args.explain,
                explain_output=args.explain_output, _prediction_mode='Auto')
        else:
            routing_decision = "Coverage below threshold — used universal model."
            results = predict_universal(
                args.input, force_sector=sector,
                explain=args.explain, explain_output=args.explain_output,
                _prediction_mode='Auto', _precomputed_coverage=coverage)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        _maybe_emit_report(results, sector,
                           routing_decision=routing_decision, args=args)

    elif args.mode == 'list_heads':
        print("\nMulti-head model architecture:")
        print(f"{'Sector': <12} {'Model file': <55} {'Trained?'}")
        print("-" * 85)
        for sector_name, cfg in SECTOR_CONFIG.items():
            model_file = cfg['model_path']
            trained = "Yes" if Path(model_file).exists() else "No"
            print(f"{sector_name: <12} {model_file: <55} {trained}")