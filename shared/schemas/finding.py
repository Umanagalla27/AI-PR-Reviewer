from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from shared.db.models import SeverityLevel

class FindingBase(BaseModel):
    agent: str
    file_path: str
    line_number: Optional[int] = None
    severity: SeverityLevel
    message: str
    suggestion: Optional[str] = None

class FindingCreate(FindingBase):
    pass

class FindingResponse(FindingBase):
    id: UUID
    pr_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class StylePatternBase(BaseModel):
    pattern_type: str
    description: str

class StylePatternCreate(StylePatternBase):
    pass

class StylePatternResponse(StylePatternBase):
    id: UUID
    repo_full_name: str
    frequency: int
    last_seen: datetime

    class Config:
        from_attributes = True
