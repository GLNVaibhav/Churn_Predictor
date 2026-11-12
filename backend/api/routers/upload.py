from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, status, Response
import uuid
import tempfile
from datetime import datetime
from pathlib import Path

from ..auth import CurrentUser, owns_resource, require_user
from ..dependencies import get_execution_repository, get_upload_service
from ..dependencies import get_upload_storage
from ..schemas.upload import UploadResponse
from backend.config import settings

router = APIRouter(tags=["Upload"])


@router.delete("/uploads/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(
    upload_id: str,
    repo=Depends(get_execution_repository),
    storage=Depends(get_upload_storage),
    user: CurrentUser = Depends(require_user),
):
    record = repo.load(upload_id)
    if not isinstance(record, dict) or "filename" not in record or not owns_resource(record, user):
        raise HTTPException(status_code=404, detail="Upload not found")
    try:
        storage.delete(upload_id, record)
        repo.delete(upload_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Upload could not be deleted at this time.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Dataset",
)
async def upload_file(
    file: UploadFile = File(...),
    repo = Depends(get_execution_repository),
    service = Depends(get_upload_service),
    user: CurrentUser = Depends(require_user),
    storage = Depends(get_upload_storage),
):
    filename = Path((file.filename or "").replace("\\", "/")).name
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    contents = await file.read(settings.MAX_UPLOAD_SIZE + 1)
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="CSV files must be 10 MB or smaller")
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded CSV is empty")

    upload_id = uuid.uuid4().hex
    try:
        with tempfile.TemporaryDirectory(prefix="ucif-profile-") as temp_dir:
            profile_path = Path(temp_dir) / filename
            profile_path.write_bytes(contents)
            profiling = service.process_upload(profile_path, filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The uploaded CSV could not be parsed.") from exc
    try:
        storage_key = storage.save(upload_id, filename, contents)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dataset storage is temporarily unavailable.") from exc

    # Persist upload metadata in repository (using upload_id as key)
    try:
        repo.save(upload_id, {
            "upload_id": upload_id,
            "owner_id": user.user_id,
            "storage_key": storage_key,
            **profiling,
        })
    except Exception as exc:
        storage.delete(upload_id, {"filename": filename, "storage_key": storage_key})
        raise HTTPException(status_code=503, detail="Upload metadata could not be persisted.") from exc

    return UploadResponse(
        upload_id=upload_id,
        status="READY",
        filename=filename,
        rows=profiling["rows"],
        columns=profiling["columns"],
        null_counts=profiling["null_counts"],
        dtypes=profiling["dtypes"],
        sector=profiling.get("sector"),
        sector_detection=profiling.get("sector_detection"),
        coverage_score=profiling.get("coverage_score"),
        concept_confidence=profiling.get("concept_confidence"),
        preview_rows=profiling.get("preview_rows"),
        column_profiles=profiling.get("column_profiles"),
        target_column=profiling.get("target_column"),
        missing_critical=profiling.get("missing_critical"),
        warnings=profiling.get("warnings"),
        created_at=profiling["created_at"],
    )
