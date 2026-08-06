from __future__ import annotations
from ..domain.models import ProfilingResult


class ProfileCache:
    """In-process profile cache keyed by fingerprint and artifact versions."""
    def __init__(self) -> None: self._store: dict[tuple[str, str], ProfilingResult] = {}
    def get(self, fingerprint: str, version_key: str) -> ProfilingResult | None: return self._store.get((fingerprint, version_key))
    def put(self, result: ProfilingResult, version_key: str) -> None: self._store[(result.dataset.fingerprint.value, version_key)] = result
