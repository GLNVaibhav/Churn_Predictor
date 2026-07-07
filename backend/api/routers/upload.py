from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, status
import uuid
from datetime import datetime
from pathlib import Path

from ..dependencies import get_execution_repository, get_upload_service
from ..schemas.upload import UploadResponse
from backend.config import settings

router = APIRouter(tags=["Upload"])

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
):
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    upload_id = uuid.uuid4().hex
    upload_dir = Path(settings.UPLOAD_ROOT) / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename

    # Save uploaded file
    contents = await file.read()
    file_path.write_bytes(contents)

    # Process profiling and business logic via service
    profiling = service.process_upload(file_path, file.filename)

    # Persist upload metadata in repository (using upload_id as key)
    repo.save(upload_id, {"upload_id": upload_id, **profiling})

    return UploadResponse(
        upload_id=upload_id,
        status="READY",
        filename=file.filename,
        rows=profiling["rows"],
        columns=profiling["columns"],
        null_counts=profiling["null_counts"],
        dtypes=profiling["dtypes"],
        sector=profiling.get("sector"),
        coverage_score=profiling.get("coverage_score"),
        concept_confidence=profiling.get("concept_confidence"),
        preview_rows=profiling.get("preview_rows"),
        warnings=profiling.get("warnings"),
        created_at=profiling["created_at"],
    )