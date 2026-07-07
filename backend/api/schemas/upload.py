from pydantic import BaseModel

class UploadResponse(BaseModel):
    upload_id: str
    status: str = "PENDING"
    detail: str | None = None
