import os
import json
from typing import Dict, List, Any, Optional

from .repository_protocol import ExecutionRepositoryProtocol


class ExecutionRepository:
    """File-based ``ExecutionRepositoryProtocol`` implementation.

    Stores JSON at ``{base_dir}/{execution_id}.json``.  Designed to be
    replaced by PostgreSQL/Redis backends implementing the same protocol.
    """

    def __init__(self, base_dir: str = "data/runs") -> None:
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _file_path(self, execution_id: str) -> str:
        return os.path.join(self.base_dir, f"{execution_id}.json")

    def save(self, execution_id: str, data: Dict[str, Any]) -> None:
        path = self._file_path(execution_id)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, path)

    def load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        path = self._file_path(execution_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def delete(self, execution_id: str) -> bool:
        path = self._file_path(execution_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def list_executions(self) -> List[Dict[str, Any]]:
        summaries: List[Dict[str, Any]] = []
        if not os.path.isdir(self.base_dir):
            return summaries
        for fname in os.listdir(self.base_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self.base_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                execution = data.get("execution") if isinstance(data.get("execution"), dict) else data
                execution_id = execution.get("execution_id") or fname.replace(".json", "")
                dataset = data.get("dataset") or {}
                summaries.append({
                    "execution_id": execution_id,
                    "status": execution.get("status"),
                    "created_at": execution.get("created_at") or execution.get("started_at"),
                    "started_at": execution.get("started_at"),
                    "completed_at": execution.get("completed_at"),
                    "execution_time_ms": execution.get("execution_time_ms"),
                    "filename": dataset.get("filename"),
                    "sector": dataset.get("sector"),
                    "progress": (data.get("pipeline_state") or data.get("pipeline") or {}).get("progress"),
                })
            except Exception:
                continue
        summaries.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return summaries
