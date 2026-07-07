from pydantic import BaseModel
from typing import List

class FrameworkResponse(BaseModel):
    framework_version: str
    runtime_version: str
    available_modules: List[str]
    supported_sectors: List[str]
    contract_version: str
