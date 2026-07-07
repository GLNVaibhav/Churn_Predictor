import os
import json
from typing import Dict, List, Any, Optional

class ExecutionRepository:
    """Repository for persisting execution context as JSON files.
    Stores files under ``outputs/runs`` relative to the project root.
    """

    def __init__(self, base_dir: str = "outputs/runs") -> None:
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _file_path(self, execution_id: str) -> str:
        return os.path.join(self.base_dir, f"{execution_id}.json")

    def save(self, execution_id: str, data: Dict[str, Any]) -> None:
        """Write *data* to ``<base_dir>/<execution_id>.json`` atomically."""
        path = self._file_path(execution_id)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)

    def load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Read execution data; return ``None`` if not found or invalid."""
        path = self._file_path(execution_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def list_executions(self) -> List[Dict[str, Any]]:
        """Return a summary list of all executions.
        Each entry contains a minimal set of metadata for the GET /executions endpoint.
        """
        summaries: List[Dict[str, Any]] = []
        for fname in os.listdir(self.base_dir):
            if not fname.endswith('.json'):
                continue
            path = os.path.join(self.base_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                summaries.append({
                    "execution_id": data.get("execution_id"),
                    "status": data.get("status"),
                    "created_at": data.get("created_at"),
                    "completed_at": data.get("completed_at"),
                    "progress": data.get("pipeline_state", {}).get("progress"),
                })
            except Exception:
                continue
        summaries.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return summaries
