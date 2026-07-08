#!/usr/bin/env python3
"""
scripts/generate_golden_contract.py
══════════════════════════════════════════════════════════════════════
Generate regression artifacts for the Backend ↔ Universal_Churn boundary.

Outputs:
    golden_framework_output.json  — raw framework output (pre-normalization)
    golden_execution_result.json  — normalized backend ExecutionResult

Usage::

    python scripts/generate_golden_contract.py
    python scripts/generate_golden_contract.py --input tests/golden_telecom.csv --mode auto
    python scripts/generate_golden_contract.py --output-dir backend/tests/golden
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path when run as a script
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.adapters import FrameworkAdapter
from backend.models.execution_result import ExecutionResult, extract_raw_framework_output


DEFAULT_INPUT = REPO_ROOT / "tests" / "golden_telecom.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "backend" / "tests" / "golden"


def _json_dump(obj: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True, default=str, ensure_ascii=False)
        fh.write("\n")
    print(f"Wrote {path}", flush=True)


def generate(
    input_path: Path,
    mode: str = "auto",
    sector: str | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[dict, dict]:
    adapter = FrameworkAdapter()
    execution_result: ExecutionResult = adapter.execute(
        input_path=str(input_path),
        sector=sector,
        mode=mode,
        explain=False,
    )

    raw_output = extract_raw_framework_output(execution_result)
    normalized = execution_result.to_dict(include_dataframe=True)

    _json_dump(raw_output, output_dir / "golden_framework_output.json")
    _json_dump(normalized, output_dir / "golden_execution_result.json")

    return raw_output, normalized


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate golden contract regression artifacts."
    )
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help=f"Input CSV (default: {DEFAULT_INPUT})",
    )
    parser.add_argument("--mode", default="auto", choices=["auto", "sector", "universal"])
    parser.add_argument("--sector", default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: input file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        generate(
            input_path=args.input,
            mode=args.mode,
            sector=args.sector,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
