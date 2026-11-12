import sys
from types import SimpleNamespace

from backend.services.upload_storage import FilesystemUploadStorage, S3UploadStorage


def test_filesystem_upload_storage_roundtrip_and_delete(tmp_path):
    storage = FilesystemUploadStorage(tmp_path)
    key = storage.save("upload-1", "customers.csv", b"id,churn\n1,0\n")
    record = {"filename": "customers.csv", "storage_key": key}

    path, temporary = storage.materialize("upload-1", record)
    assert path.read_bytes() == b"id,churn\n1,0\n"
    assert temporary is False

    storage.delete("upload-1", record)
    assert not path.exists()


def test_filesystem_storage_rejects_path_traversal(tmp_path):
    storage = FilesystemUploadStorage(tmp_path)
    try:
        storage.materialize("upload-1", {"filename": "..\\outside.csv"})
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal must be rejected")


def test_filesystem_storage_rejects_windows_traversal(tmp_path):
    storage = FilesystemUploadStorage(tmp_path)
    try:
        storage.materialize("upload-1", {"filename": "..\\outside.csv"})
    except ValueError:
        pass
    else:
        raise AssertionError("Windows path traversal must be rejected")


def test_s3_storage_adapter_uses_scoped_keys_and_materializes(monkeypatch, tmp_path):
    class FakeS3:
        def __init__(self):
            self.objects = {}

        def put_object(self, *, Bucket, Key, Body, ContentType):
            self.objects[(Bucket, Key)] = Body

        def download_file(self, bucket, key, filename):
            from pathlib import Path
            Path(filename).write_bytes(self.objects[(bucket, key)])

        def delete_object(self, *, Bucket, Key):
            self.objects.pop((Bucket, Key), None)

    client = FakeS3()
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: client))
    storage = S3UploadStorage("private-test-bucket")
    key = storage.save("upload-1", "customers.csv", b"id,churn\n1,0\n")
    record = {"filename": "customers.csv", "storage_key": key}

    materialized, temporary = storage.materialize("upload-1", record)
    assert temporary is True
    assert materialized.read_bytes() == b"id,churn\n1,0\n"
    materialized.unlink()

    storage.delete("upload-1", record)
    assert ("private-test-bucket", key) not in client.objects


def test_s3_storage_rejects_keys_from_another_upload(monkeypatch):
    class FakeS3:
        pass

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: FakeS3()))
    storage = S3UploadStorage("private-test-bucket")
    try:
        storage.materialize("upload-1", {
            "filename": "customers.csv",
            "storage_key": "uploads/upload-2/customers.csv",
        })
    except ValueError:
        pass
    else:
        raise AssertionError("cross-upload storage key must be rejected")
