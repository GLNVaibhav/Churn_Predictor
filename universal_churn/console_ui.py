"""Reusable, dependency-free rendering primitives for the UCIF CLI."""
from __future__ import annotations

from datetime import datetime

WIDTH = 78


def _write(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))


def rule(char: str = "=") -> None:
    _write(char * WIDTH)


def print_banner(execution_id: str, mode: str, dataset: str, pipeline_version: str) -> None:
    rule("=")
    _write("        UNIVERSAL CHURN INTELLIGENCE FRAMEWORK (UCIF)")
    _write("                 Enterprise Intelligence Console")
    rule("=")
    print_metric("Execution ID", execution_id)
    print_metric("Pipeline Version", pipeline_version)
    print_metric("Execution Mode", mode.upper())
    print_metric("Input Dataset", dataset)
    print_metric("Execution Timestamp", datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"))
    rule("-")


def print_stage_header(number: int, title: str, purpose: str) -> None:
    _write("")
    rule("-")
    _write(f"STAGE {number} | {title.upper()}")
    _write(f"Purpose: {purpose}")
    rule("-")


def print_metric(label: str, value: object) -> None:
    _write(f"  {label:<30} {value}")


def print_success(message: str) -> None:
    _write(f"  [OK] {message}")


def print_warning(message: str) -> None:
    _write(f"  [WARN] {message}")


def print_error(message: str) -> None:
    _write(f"  [ERROR] {message}")


def print_bar(label: str, value: float, width: int = 22) -> None:
    filled = max(0, min(width, round(value * width)))
    _write(f"  {label:<24} {'#' * filled}{'.' * (width - filled)} {value:>6.1%}")


def print_count_bar(label: str, count: int, maximum: int) -> None:
    width = 22
    filled = round(width * count / maximum) if maximum else 0
    _write(f"  {label:<24} {'#' * filled}{'.' * (width - filled)} {count}")


def print_timing(seconds: float) -> None:
    print_metric("Time Taken", f"{seconds:.3f} sec")


def print_artifact(path: str, purpose: str | None = None) -> None:
    print_success(path)
    if purpose:
        print_metric("Purpose", purpose)


def print_summary(title: str = "EXECUTION SUMMARY") -> None:
    _write("")
    rule("=")
    _write(title)
    rule("=")
