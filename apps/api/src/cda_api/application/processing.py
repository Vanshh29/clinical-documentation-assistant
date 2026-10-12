"""State changes made by the processing pipeline (worker), as opposed to the clinician."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cda_api.adapters.db.models import LlmCall, Note, Summary
from cda_api.application import audit
from cda_api.domain.enums import AuditAction, NoteStatus
from cda_api.domain.errors import NotFound
from cda_api.domain.state_machine import ensure_transition
from cda_api.domain.summary_schema import SCHEMA_VERSION, ClinicalSummary


async def _locked_note(session: AsyncSession, note_id: uuid.UUID) -> Note:
    note = (
        await session.execute(select(Note).where(Note.id == note_id).with_for_update())
    ).scalar_one_or_none()
    if note is None:
        raise NotFound("note not found")
    return note


async def start_processing(session: AsyncSession, note_id: uuid.UUID) -> Note:
    note = await _locked_note(session, note_id)
    note.status = ensure_transition(NoteStatus(note.status), NoteStatus.PROCESSING).value
    await audit.record(
        session,
        AuditAction.PROCESSING_STARTED,
        "note",
        note.id,
        details={"generation": note.generation},
    )
    return note


async def complete_processing(
    session: AsyncSession,
    note_id: uuid.UUID,
    summary: ClinicalSummary,
    *,
    model: str,
    prompt_version: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    retries: int,
    cost_usd: Decimal,
    request_id: str | None = None,
) -> Summary:
    note = await _locked_note(session, note_id)
    note.status = ensure_transition(NoteStatus(note.status), NoteStatus.PENDING_REVIEW).value
    row = Summary(
        note_id=note.id,
        generation=note.generation,
        schema_version=SCHEMA_VERSION,
        model=model,
        prompt_version=prompt_version,
        content=summary.model_dump(mode="json"),
    )
    session.add(row)
    session.add(
        LlmCall(
            note_id=note.id,
            model=model,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            retries=retries,
            cost_usd=cost_usd,
            outcome="ok",
        )
    )
    await session.flush()
    await audit.record(
        session,
        AuditAction.SUMMARY_GENERATED,
        "summary",
        row.id,
        request_id=request_id,
        model=model,
        prompt_version=prompt_version,
        schema_version=SCHEMA_VERSION,
        details={"generation": note.generation, "retries": retries},
    )
    return row


async def fail_processing(
    session: AsyncSession,
    note_id: uuid.UUID,
    reason: str,
    *,
    model: str,
    prompt_version: str,
    retries: int,
    request_id: str | None = None,
) -> Note:
    """`reason` must be a short machine-readable cause, never note text."""
    note = await _locked_note(session, note_id)
    note.status = ensure_transition(NoteStatus(note.status), NoteStatus.FAILED_VALIDATION).value
    note.failure_reason = reason
    session.add(
        LlmCall(
            note_id=note.id,
            model=model,
            prompt_version=prompt_version,
            retries=retries,
            outcome="failed_validation",
        )
    )
    await audit.record(
        session,
        AuditAction.PROCESSING_FAILED,
        "note",
        note.id,
        request_id=request_id,
        model=model,
        prompt_version=prompt_version,
        schema_version=SCHEMA_VERSION,
        details={"reason": reason, "retries": retries},
    )
    return note
