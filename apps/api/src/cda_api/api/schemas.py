import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from cda_api.domain.enums import NoteStatus, Role


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    display_name: str


class NoteCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    body: str = Field(min_length=20)
    title: str | None = Field(default=None, max_length=200)
    language: str = Field(default="auto", pattern="^(de|en|auto)$")
    source: str = Field(default="paste", pattern="^(paste|upload)$")


class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    generation: int
    schema_version: str
    model: str
    prompt_version: str
    content: dict[str, Any]
    edited_content: dict[str, Any] | None
    approved_content: dict[str, Any] | None
    diff: dict[str, Any] | None
    rejection_reason: str | None
    reviewed_at: datetime | None
    created_at: datetime


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    language: str
    source: str
    status: NoteStatus
    failure_reason: str | None
    generation: int
    created_at: datetime
    updated_at: datetime


class NoteDetail(NoteOut):
    body: str
    summary: SummaryOut | None


class NoteList(BaseModel):
    items: list[NoteOut]
    total: int


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class ErasureResult(BaseModel):
    notes_deleted: int


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    occurred_at: datetime
    actor_id: uuid.UUID | None
    actor_role: str | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    request_id: str | None
    model: str | None
    prompt_version: str | None
    schema_version: str | None
    details: dict[str, Any]


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int


class MetricsOut(BaseModel):
    notes_total: int
    notes_by_status: dict[str, int]
    approval_rate: float | None
    edit_rate: float | None
    mean_edit_ratio: float | None
    validation_failure_rate: float | None
    llm_calls: int
    llm_latency_ms_p50: float | None
    llm_latency_ms_p95: float | None
    time_to_summary_s_p50: float | None
    time_to_summary_s_p95: float | None
    input_tokens: int
    output_tokens: int
    cost_usd_total: float
    cost_usd_per_note: float | None
