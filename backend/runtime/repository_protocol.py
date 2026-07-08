"""
backend.runtime.repository_protocol
══════════════════════════════════════════════════════════════════════
Repository interface — designed for future PostgreSQL/Redis backends.
Current implementation: ``FileExecutionRepository``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class ExecutionRepositoryProtocol(Protocol):
    """Persistence contract for ``ExecutionRecord`` lifecycle data."""

    def save(self, execution_id: str, data: Dict[str, Any]) -> None: ...

    def load(self, execution_id: str) -> Optional[Dict[str, Any]]: ...

    def list_executions(self) -> List[Dict[str, Any]]: ...

    def delete(self, execution_id: str) -> bool: ...
