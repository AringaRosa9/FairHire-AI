from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from fairhire_domain.access import Role
from pydantic import BaseModel, ConfigDict, Field


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    code: str | None = None


class Pagination(BaseModel):
    page: int = 1
    page_size: int = 25
    total: int


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    poll_url: str
    submitted_at: datetime


class SessionResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    organization_id: str
    organization_name: str
    role: Role
    permissions: list[str]


class AISystemBase(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=200)]
    purpose: Annotated[str, Field(min_length=10, max_length=4000)]
    lifecycle_status: Literal["draft", "trial", "active", "retired"] = "draft"
    release_status: Literal[
        "approved", "review_required", "blocked", "draft", "insufficient_evidence"
    ] = "draft"
    provider_type: Literal["internal", "third_party"]
    provider_name: str | None = None
    jurisdictions: Annotated[list[str], Field(min_length=1)]
    owner_name: Annotated[str, Field(min_length=2, max_length=160)]
    next_review_at: datetime | None = None


class AISystemCreate(AISystemBase):
    pass


class AISystemResponse(AISystemBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    assessment_version: int


class AISystemListResponse(Pagination):
    items: list[AISystemResponse]
