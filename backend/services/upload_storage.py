"""Local and S3-compatible durable storage for uploaded source datasets."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Protocol

from backend.config import settings


class UploadStorage(Protocol):
    def save(self, upload_id: str, filename: str, contents: bytes) -> str: ...
    def materialize(self, upload_id: str, record: dict) -> tuple[Path, bool]: ...
    def delete(self, upload_id: str, record: dict) -> None: ...


class FilesystemUploadStorage:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def save(self, upload_id: str, filename: str, contents: bytes) -> str:
        safe_name = Path(filename.replace("\\", "/")).name
        path = self.root / upload_id / safe_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        return f"{upload_id}/{safe_name}"

    def materialize(self, upload_id: str, record: dict) -> tuple[Path, bool]:
        raw_name = str(record.get("filename", ""))
        filename = Path(raw_name.replace("\\", "/")).name
        if not filename or raw_name != filename:
            raise ValueError("Invalid upload filename")
        path = (self.root / upload_id / filename).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid upload storage key")
        return path, False

    def delete(self, upload_id: str, record: dict) -> None:
        path, _ = self.materialize(upload_id, record)
        if path.exists():
            path.unlink()
        try:
            path.parent.rmdir()
        except OSError:
            pass


class S3UploadStorage:
    def __init__(self, bucket: str, region: str | None = None, endpoint_url: str | None = None) -> None:
        if not bucket:
            raise ValueError("S3_BUCKET is required for object storage")
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - depends on deployment extra
            raise RuntimeError("Install the boto3 production dependency") from exc
        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region or None, endpoint_url=endpoint_url or None)

    def _key(self, upload_id: str, filename: str) -> str:
        safe_name = Path(filename.replace("\\", "/")).name
        return f"uploads/{upload_id}/{safe_name}"

    def save(self, upload_id: str, filename: str, contents: bytes) -> str:
        key = self._key(upload_id, filename)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=contents, ContentType="text/csv")
        return key

    def materialize(self, upload_id: str, record: dict) -> tuple[Path, bool]:
        key = record.get("storage_key")
        if not isinstance(key, str) or key != self._key(upload_id, str(record.get("filename", ""))):
            raise ValueError("Invalid upload storage key")
        suffix = Path(str(record.get("filename", "dataset.csv"))).suffix or ".csv"
        fd, path = tempfile.mkstemp(prefix="ucif-upload-", suffix=suffix)
        os.close(fd)
        try:
            self.client.download_file(self.bucket, key, path)
        except Exception:
            Path(path).unlink(missing_ok=True)
            raise
        return Path(path), True

    def delete(self, upload_id: str, record: dict) -> None:
        key = record.get("storage_key")
        if isinstance(key, str) and key == self._key(upload_id, str(record.get("filename", ""))):
            self.client.delete_object(Bucket=self.bucket, Key=key)


def create_upload_storage() -> UploadStorage:
    if settings.OBJECT_STORAGE_BACKEND == "s3":
        return S3UploadStorage(
            bucket=os.getenv("S3_BUCKET", ""),
            region=os.getenv("AWS_REGION"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        )
    if settings.OBJECT_STORAGE_BACKEND != "filesystem":
        raise ValueError("OBJECT_STORAGE_BACKEND must be filesystem or s3")
    return FilesystemUploadStorage(settings.UPLOAD_ROOT)
