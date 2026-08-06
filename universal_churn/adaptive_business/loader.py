"""Validated, offline loader for optional business-context JSON files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_REQUIRED = {"category", "description", "severity", "confidence"}
_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def load_business_context(path: str | None) -> tuple[dict[str, Any], ...]:
    """Load and validate a context document; absence deliberately yields no evidence."""
    if path is None:
        return ()
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Business context file was not found: {source}")
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Business context is not valid JSON: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("events"), list):
        raise ValueError("Business context must be an object containing an 'events' list.")
    validated = []
    for index, event in enumerate(document["events"]):
        if not isinstance(event, dict) or not _REQUIRED.issubset(event):
            raise ValueError(f"Context event {index} must contain: {', '.join(sorted(_REQUIRED))}.")
        severity = str(event["severity"]).upper()
        if severity not in _SEVERITIES:
            raise ValueError(f"Context event {index} has unsupported severity '{event['severity']}'.")
        try:
            confidence = float(event["confidence"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Context event {index} confidence must be numeric.") from exc
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Context event {index} confidence must be between 0 and 1.")
        validated.append({**event, "severity": severity, "confidence": confidence})
    return tuple(validated)
