from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["Upload"])


@router.post(
    "/upload",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Upload Dataset",
)
async def upload_file():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Upload endpoint not yet implemented.",
    )