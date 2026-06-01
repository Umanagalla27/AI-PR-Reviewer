from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class PRBase(BaseModel):
    repo_full_name: str
    pr_number: int
    head_sha: str
    base_sha: str
    author: str

class PRCreate(PRBase):
    pass

class PRResponse(PRBase):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PullRequestEvent(BaseModel):
    action: str
    number: int
    pull_request: dict
    repository: dict
