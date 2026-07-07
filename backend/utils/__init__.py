"""
backend.utils
══════════════════════════════════════════════════════════════════════
Small, dependency-free helpers shared by ``backend.contracts`` and
``backend.mappers``. Nothing here touches ``universal_churn`` — these
are backend-local mechanics only (timestamps, ID generation, recursive
dict conversion for dataclasses), never framework computation.
"""
from __future__ import annotations

import uuid
from dataclasses import is_dataclass, fields
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_timestamp() -> str:
    """UTC timestamp, formatted identically to the rest of the
    codebase (see ``universal_churn.utils._utc_timestamp``), so
    backend-generated timestamps read consistently alongside
    framework-generated ones."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def new_execution_id() -> str:
    """Generate a new, unique execution identifier."""
    return f"exec_{uuid.uuid4().hex}"


def to_serializable(value: Any) -> Any:
    """
    Recursively convert dataclasses (including nested ones, lists,
    tuples, dicts, and Enums) into plain, JSON-serializable Python
    types (dict / list / str / int / float / bool / None).

    This is intentionally more permissive than ``dataclasses.asdict``:
    it also normalizes Enums to their ``.value`` and leaves already-
    plain values untouched, which lets every contract in
    ``backend.contracts`` implement ``to_dict()`` as a one-liner that
    calls this function.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_serializable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: to_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_serializable(v) for v in value]
    return value


def safe_get(obj: Any, name: str, default: Any = None) -> Any:
    """
    Read an attribute or dict key from ``obj`` without caring which
    shape it is — many framework outputs are plain dicts (coverage.py,
    quality_gate.py) while others are typed dataclasses (RoutingDecision,
    DecisionAssessment). Mappers use this instead of hand-writing an
    ``isinstance`` check at every call site.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)
