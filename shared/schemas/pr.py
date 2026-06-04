from pydantic import BaseModel, ConfigDict
from typing import List
from datetime import datetime
from uuid import UUID
from shared.schemas.finding import FindingBase


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

    model_config = ConfigDict(from_attributes=True)


class LearnMergedPRRequest(PRBase):
    installation_id: int


class ReviewStartRequest(PRBase):
    pr_id: UUID
    installation_id: int


class ReviewPostRequest(PRBase):
    pr_id: UUID
    installation_id: int
    findings: List[FindingBase]


class PRProcessRequest(PRBase):
    action: str
    installation_id: int
    merged: bool


class PRProcessResponse(BaseModel):
    pr_id: UUID
    status: str


class PullRequestEvent(BaseModel):
    action: str
    number: int
    pull_request: dict
    repository: dict
