"""Analysis router placeholder for FastAPI transport layer.
This stub ensures imports succeed while the actual analysis logic is pending.
"""

from fastapi import APIRouter, HTTPException, status

router = APIRouter()

@router.post("/analyze", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def start_analysis():
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Analysis endpoint not yet implemented")
