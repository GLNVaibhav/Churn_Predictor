"""Explicit PostgreSQL/S3 retention purge; intended for a scheduled host job."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from backend.config import settings
from backend.runtime.postgres_repository import PostgresExecutionRepository
from backend.services.upload_storage import create_upload_storage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--older-than-days", type=int, required=True)
    args = parser.parse_args()
    if args.older_than_days < 1:
        parser.error("--older-than-days must be at least one")
    if not settings.DATABASE_URL or settings.OBJECT_STORAGE_BACKEND != "s3":
        parser.error("Retention purge requires DATABASE_URL and OBJECT_STORAGE_BACKEND=s3")

    repository = PostgresExecutionRepository(settings.DATABASE_URL)
    storage = create_upload_storage()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.older_than_days)
    removed = 0
    for record_id, record in repository.list_expired_records(cutoff):
        if record.get("upload_id") and record.get("filename"):
            storage.delete(str(record["upload_id"]), record)
        if repository.delete(record_id):
            removed += 1
    print(f"Removed {removed} expired UCIF records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
