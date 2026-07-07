from pydantic import BaseModel
from typing import List, Dict, Optional

class UploadResponse(BaseModel):
    upload_id: str
    status: str = "READY"
    filename: str
    rows: int
    columns: int
    null_counts: Dict[str, int]
    dtypes: Dict[str, str]
    sector: Optional[str] = None
    coverage_score: Optional[float] = None
    concept_confidence: Optional[float] = None
    preview_rows: Optional[List[Dict]] = None  # first 5 rows
    warnings: Optional[List[str]] = None
    created_at: str
    detail: Optional[str] = None
