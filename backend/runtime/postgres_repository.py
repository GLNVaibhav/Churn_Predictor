"""PostgreSQL-backed execution/upload metadata repository.

The JSON file repository remains the zero-configuration local backend. This
implementation uses PostgreSQL JSONB and creates its small metadata table on
startup; production migrations should be managed by the deployment process.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


class PostgresExecutionRepository:
    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("DATABASE_URL is required for PostgreSQL storage")
        try:
            import psycopg
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover - depends on deployment extra
            raise RuntimeError("Install the psycopg[binary] production dependency") from exc
        self._psycopg = psycopg
        self._jsonb = Jsonb
        self._dsn = dsn
        self.initialize()

    def _connect(self):
        return self._psycopg.connect(self._dsn, connect_timeout=5)

    def initialize(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ucif_records (
                    record_id TEXT PRIMARY KEY,
                    owner_id TEXT,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS ucif_records_owner_idx ON ucif_records (owner_id)")

    def save(self, execution_id: str, data: Dict[str, Any]) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", execution_id):
            raise ValueError("Invalid record identifier")
        safe_data = json.loads(json.dumps(data, ensure_ascii=False, default=str))
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ucif_records (record_id, owner_id, data)
                VALUES (%s, %s, %s)
                ON CONFLICT (record_id) DO UPDATE SET
                    owner_id = EXCLUDED.owner_id,
                    data = EXCLUDED.data,
                    updated_at = now()
            """, (execution_id, safe_data.get("owner_id"), self._jsonb(safe_data)))

    def load(self, execution_id: str) -> Optional[Dict[str, Any]]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", execution_id):
            return None
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT data FROM ucif_records WHERE record_id = %s", (execution_id,))
            row = cur.fetchone()
            return row[0] if row and isinstance(row[0], dict) else None

    def delete(self, execution_id: str) -> bool:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", execution_id):
            return False
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM ucif_records WHERE record_id = %s", (execution_id,))
            return cur.rowcount > 0

    def list_expired_records(self, cutoff: datetime) -> List[tuple[str, Dict[str, Any]]]:
        """Return expired, non-running records for an explicitly scheduled purge."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT record_id, data
                FROM ucif_records
                WHERE created_at < %s
                  AND COALESCE(data->>'status', data->'execution'->>'status', '')
                      NOT IN ('PENDING', 'RUNNING')
            """, (cutoff,))
            return [(record_id, data) for record_id, data in cur.fetchall() if isinstance(data, dict)]

    def list_executions(self) -> List[Dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT record_id, owner_id, data FROM ucif_records")
            rows = cur.fetchall()
        summaries = []
        for record_id, owner_id, data in rows:
            if not isinstance(data, dict):
                continue
            execution = data.get("execution") if isinstance(data.get("execution"), dict) else data
            if not execution.get("status"):
                continue
            dataset = data.get("dataset") or {}
            pipeline = data.get("pipeline_state") or data.get("pipeline") or {}
            summaries.append({
                "execution_id": execution.get("execution_id") or record_id,
                "owner_id": owner_id,
                "status": execution.get("status"),
                "created_at": execution.get("created_at") or execution.get("started_at"),
                "started_at": execution.get("started_at"),
                "completed_at": execution.get("completed_at"),
                "execution_time_ms": execution.get("execution_time_ms"),
                "filename": dataset.get("filename") or data.get("filename"),
                "sector": dataset.get("sector") or data.get("sector"),
                "progress": pipeline.get("progress"),
            })
        return sorted(summaries, key=lambda item: item.get("created_at") or "", reverse=True)
