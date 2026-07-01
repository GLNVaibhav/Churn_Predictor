#!/usr/bin/env python3
"""
validate_framework.py
══════════════════════════════════════════════════════════════════════
Official validation command for the Universal Churn Predictor
(Version 6 — Chunk 4: Framework Validation, Regression & Benchmarking).

This script does NOT change prediction behaviour. It only observes,
exercises, and reports on the existing pipeline (schema_resolution ->
business_concepts -> feature_engineering -> coverage -> quality_gate
-> routing -> sector_pipeline / universal_pipeline -> cli).

Usage
-----
    python validate_framework.py                 # run everything
    python validate_framework.py --skip-training  # skip retraining steps
    python validate_framework.py --fast           # skip pytest + benchmarking

Exit code is 0 iff every check PASSED.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PY = sys.executable


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    elapsed_s: float = 0.0


RESULTS: list[CheckResult] = []


def _run(name: str, fn, *args, **kwargs) -> CheckResult:
    start = time.time()
    try:
        ok, detail = fn(*args, **kwargs)
        result = CheckResult(name=name, passed=ok, detail=detail, elapsed_s=time.time() - start)
    except Exception as exc:  # noqa: BLE001 — a failing check must not crash the validator
        result = CheckResult(name=name, passed=False, detail=f"EXCEPTION: {exc}",
                             elapsed_s=time.time() - start)
    RESULTS.append(result)
    icon = "✔" if result.passed else "✖"
    print(f"  [{icon}] {name:<38} ({result.elapsed_s:5.2f}s)  {result.detail}")
    return result


def _subprocess(cmd: list[str], timeout: int = 600) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout)
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-15:])
    return proc.returncode, tail


# ══════════════════════════════════════════════════════════════════
# 1. IMPORT VALIDATION
# ══════════════════════════════════════════════════════════════════

def check_imports() -> tuple[bool, str]:
    modules = [
        "universal_churn", "universal_churn.cli", "universal_churn.config",
        "universal_churn.preprocessing", "universal_churn.schema_resolution",
        "universal_churn.business_concepts", "universal_churn.concept_confidence",
        "universal_churn.canonical_fields", "universal_churn.coverage",
        "universal_churn.quality_gate", "universal_churn.routing",
        "universal_churn.feature_engineering", "universal_churn.sector_pipeline",
        "universal_churn.universal_pipeline", "universal_churn.reporting",
        "universal_churn.explainability", "universal_churn.utils",
        "universal_churn.drift_monitoring", "universal_churn.feature_transforms",
        "universal_churn.validation",
    ]
    code = (
        "import importlib, sys\n"
        f"mods = {modules!r}\n"
        "failed = []\n"
        "for m in mods:\n"
        "    try:\n"
        "        importlib.import_module(m)\n"
        "    except Exception as exc:\n"
        "        failed.append(f'{m}: {exc}')\n"
        "if failed:\n"
        "    print('IMPORT_FAILURES:' + ' | '.join(failed))\n"
        "    sys.exit(1)\n"
        "print('all modules imported OK')\n"
    )
    rc, tail = _subprocess([PY, "-c", code])
    return rc == 0, tail


# ══════════════════════════════════════════════════════════════════
# 2. PY_COMPILE VALIDATION
# ══════════════════════════════════════════════════════════════════

def check_py_compile() -> tuple[bool, str]:
    targets = ["universal_churn", "main.py", "tests", "predict"]
    rc, tail = _subprocess([PY, "-m", "py_compile"] + [
        str(p) for target in targets
        for p in ([Path(target)] if Path(REPO_ROOT / target).is_file()
                 else sorted((REPO_ROOT / target).rglob("*.py")))
    ])
    return rc == 0, ("all files compiled" if rc == 0 else tail)


# ══════════════════════════════════════════════════════════════════
# 3. GOLDEN DATASET VALIDATION
# ══════════════════════════════════════════════════════════════════

GOLDEN_FILES = {
    "telecom": "tests/golden_telecom.csv",
    "banking": "tests/golden_banking.csv",
    "ecommerce": "tests/golden_ecommerce.csv",
    "healthcare": "tests/golden_healthcare.csv",
}

EXPECTED_PREDICTION_COLUMNS = {
    "CustomerID", "Predicted_Churn", "Churn_Probability", "Risk_Level",
    "Prediction_Model", "Prediction_Mode", "Coverage_Score", "Coverage_Status",
}


def check_golden_datasets() -> tuple[bool, str]:
    import pandas as pd
    failures = []
    for sector, path in GOLDEN_FILES.items():
        out_path = REPO_ROOT / f"outputs/results/validation_golden_{sector}.csv"
        rc, tail = _subprocess([
            PY, "main.py", "--mode", "auto", "--input", path,
            "--output", str(out_path),
        ])
        if rc != 0:
            failures.append(f"{sector}: exit={rc} :: {tail}")
            continue
        if not out_path.exists():
            failures.append(f"{sector}: output file not created")
            continue
        df = pd.read_csv(out_path)
        missing = EXPECTED_PREDICTION_COLUMNS - set(df.columns)
        if missing:
            failures.append(f"{sector}: missing columns {sorted(missing)}")
        if df.empty:
            failures.append(f"{sector}: empty result set")
    if failures:
        return False, "; ".join(failures)
    return True, f"{len(GOLDEN_FILES)}/{len(GOLDEN_FILES)} golden datasets produced valid predictions"


# ══════════════════════════════════════════════════════════════════
# 4. FEATURE PARITY VALIDATION
# ══════════════════════════════════════════════════════════════════

def check_feature_parity() -> tuple[bool, str]:
    rc, tail = _subprocess([
        PY, "-m", "pytest", "-q", "tests/test_feature_parity.py",
        "-k", "TestExactParity or TestNormalizationGuard or TestDerivationMath "
              "or TestDefaultConsistency or TestEndToEndIntegration",
    ])
    return rc == 0, tail.splitlines()[-1] if tail else "no output"


# ══════════════════════════════════════════════════════════════════
# 5. PREDICTION PARITY VALIDATION (determinism across repeated runs)
# ══════════════════════════════════════════════════════════════════

def check_prediction_parity() -> tuple[bool, str]:
    import pandas as pd
    mismatches = []
    for sector, path in GOLDEN_FILES.items():
        out_a = REPO_ROOT / f"outputs/results/_parity_a_{sector}.csv"
        out_b = REPO_ROOT / f"outputs/results/_parity_b_{sector}.csv"
        for out in (out_a, out_b):
            rc, tail = _subprocess([
                PY, "main.py", "--mode", "auto", "--input", path, "--output", str(out),
            ])
            if rc != 0:
                mismatches.append(f"{sector}: run failed ({tail})")
                break
        else:
            dfa = pd.read_csv(out_a)
            dfb = pd.read_csv(out_b)
            cols = ["Predicted_Churn", "Churn_Probability"]
            if not dfa[cols].equals(dfb[cols]):
                mismatches.append(f"{sector}: predictions differ between identical runs")
    if mismatches:
        return False, "; ".join(mismatches)
    return True, "predictions identical across repeated runs for all sectors"


# ══════════════════════════════════════════════════════════════════
# 6. CLI SMOKE TESTS
# ══════════════════════════════════════════════════════════════════

def check_cli_smoke() -> tuple[bool, str]:
    checks = [
        ["--mode", "sector", "--sector", "telecom", "--input", GOLDEN_FILES["telecom"],
         "--output", "outputs/results/validation_cli_sector.csv"],
        ["--mode", "universal", "--input", GOLDEN_FILES["banking"],
         "--output", "outputs/results/validation_cli_universal.csv"],
        ["--mode", "auto", "--input", GOLDEN_FILES["ecommerce"],
         "--output", "outputs/results/validation_cli_auto.csv"],
        ["--mode", "list_heads"],
    ]
    failures = []
    for args in checks:
        rc, tail = _subprocess([PY, "main.py"] + args)
        if rc != 0:
            failures.append(f"{' '.join(args)}: exit={rc} :: {tail}")
    if failures:
        return False, "; ".join(failures)
    return True, f"{len(checks)}/{len(checks)} CLI invocations succeeded"


# ══════════════════════════════════════════════════════════════════
# 7. PYTEST
# ══════════════════════════════════════════════════════════════════

def check_pytest() -> tuple[bool, str]:
    rc, tail = _subprocess([PY, "-m", "pytest", "-q"], timeout=900)
    summary = tail.splitlines()[-1] if tail else "no output"
    return rc == 0, summary


# ══════════════════════════════════════════════════════════════════
# 8. TRAINING SMOKE TEST
# ══════════════════════════════════════════════════════════════════

def check_training_smoke(skip: bool) -> tuple[bool, str]:
    if skip:
        return True, "skipped (--skip-training)"
    rc, tail = _subprocess([PY, "main.py", "--mode", "train_all"], timeout=900)
    return rc == 0, ("all sector + universal models trained" if rc == 0 else tail)


# ══════════════════════════════════════════════════════════════════
# 9. UNIVERSAL MODEL SMOKE TEST
# ══════════════════════════════════════════════════════════════════

def check_universal_model_smoke() -> tuple[bool, str]:
    rc, tail = _subprocess([
        PY, "main.py", "--mode", "universal", "--input", GOLDEN_FILES["healthcare"],
        "--output", "outputs/results/validation_universal_smoke.csv",
    ])
    return rc == 0, ("universal model predicted successfully" if rc == 0 else tail)


# ══════════════════════════════════════════════════════════════════
# 10. AUTO MODE SMOKE TEST
# ══════════════════════════════════════════════════════════════════

def check_auto_mode_smoke() -> tuple[bool, str]:
    failures = []
    for sector, path in GOLDEN_FILES.items():
        rc, tail = _subprocess([
            PY, "main.py", "--mode", "auto", "--input", path,
            "--output", f"outputs/results/validation_auto_{sector}.csv",
        ])
        if rc != 0:
            failures.append(f"{sector}: {tail}")
    if failures:
        return False, "; ".join(failures)
    return True, f"auto mode succeeded for all {len(GOLDEN_FILES)} sectors"


# ══════════════════════════════════════════════════════════════════
# EXTRA: REGRESSION HARNESS + BENCHMARK (supporting deliverables)
# ══════════════════════════════════════════════════════════════════

def check_regression_harness() -> tuple[bool, str]:
    from universal_churn.validation.regression import run_full_regression, print_regression_report
    results = run_full_regression()
    passed = print_regression_report(results)
    n_bootstrap = sum(1 for r in results.values() if r.bootstrap)
    detail = (f"{sum(r.passed for r in results.values())}/{len(results)} sectors clean"
             + (f" ({n_bootstrap} baseline(s) bootstrapped)" if n_bootstrap else ""))
    return passed, detail


def run_benchmark_report(fast: bool) -> None:
    if fast:
        print("\n  (benchmark skipped — --fast)")
        return
    from universal_churn.validation.benchmark import run_benchmarks, print_benchmark_report
    results = run_benchmarks(iterations=5)
    print_benchmark_report(results)


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-training", action="store_true",
                        help="Skip the training/retraining smoke test (Part 6/8).")
    parser.add_argument("--fast", action="store_true",
                        help="Skip pytest and benchmarking for a quicker run.")
    args = parser.parse_args()

    print("=" * 72)
    print("  UNIVERSAL CHURN PREDICTOR — FRAMEWORK VALIDATION")
    print("=" * 72)

    print("\n-- Structural checks --")
    _run("Import validation", check_imports)
    _run("py_compile validation", check_py_compile)

    print("\n-- Behavioural checks --")
    _run("Golden dataset validation", check_golden_datasets)
    _run("Feature parity validation", check_feature_parity)
    _run("Prediction parity validation", check_prediction_parity)
    _run("CLI smoke tests", check_cli_smoke)

    if not args.fast:
        print("\n-- Test suite --")
        _run("pytest (full suite)", check_pytest)

    print("\n-- Training / model smoke tests --")
    _run("Training smoke test (train_all)", check_training_smoke, args.skip_training)
    _run("Universal model smoke test", check_universal_model_smoke)
    _run("Auto mode smoke test", check_auto_mode_smoke)

    print("\n-- Regression & benchmarking --")
    _run("Regression harness", check_regression_harness)
    run_benchmark_report(args.fast)

    # ── Summary ──────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    n_pass = sum(1 for r in RESULTS if r.passed)
    for r in RESULTS:
        icon = "PASS" if r.passed else "FAIL"
        print(f"  [{icon}] {r.name}")
    print("-" * 72)
    overall = n_pass == len(RESULTS)
    print(f"  {n_pass}/{len(RESULTS)} checks passed — OVERALL: {'PASS' if overall else 'FAIL'}")
    print("=" * 72)
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
