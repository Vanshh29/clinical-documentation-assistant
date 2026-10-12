import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from cda_api.adapters.db.models import Note, Summary
from cda_api.application import audit
from cda_api.application.notes import enqueue_note_submitted, get_owned_note
from cda_api.domain.diff import summary_diff
from cda_api.domain.enums import AuditAction, NoteStatus
from cda_api.domain.errors import NotFound, ValidationFailed
from cda_api.domain.principal import Principal
from cda_api.domain.state_machine import ensure_transition
from cda_api.domain.summary_schema import ClinicalSummary


def current_summary(note: Note) -> Summary | None:
    return note.summaries[-1] if note.summaries else None


def _require_summary(note: Note) -> Summary:
    summary = current_summary(note)
    if summary is None:
        raise NotFound("no summary has been generated for this note")
    return summary


async def edit_summary(
    session: AsyncSession, actor: Principal, note_id: uuid.UUID, edited: ClinicalSummary
) -> Summary:
    note = await get_owned_note(session, actor, note_id, for_update=True)
    if note.status != NoteStatus.PENDING_REVIEW.value:
        raise ValidationFailed("only summaries pending review can be edited")
    summary = _require_summary(note)
    summary.edited_content = edited.model_dump(mode="json")
    await audit.record(
        session,
        AuditAction.SUMMARY_EDITED,
        "summary",
        summary.id,
        actor=actor,
        model=summary.model,
        prompt_version=summary.prompt_version,
        schema_version=summary.schema_version,
    )
    return summary


async def approve_summary(session: AsyncSession, actor: Principal, note_id: uuid.UUID) -> Summary:
    note = await get_owned_note(session, actor, note_id, for_update=True)
    summary = _require_summary(note)
    note.status = ensure_transition(NoteStatus(note.status), NoteStatus.APPROVED).value
    final = summary.edited_content or summary.content
    summary.approved_content = final
    summary.diff = summary_diff(summary.content, final)
    summary.reviewed_by = actor.user_id
    summary.reviewed_at = datetime.now(UTC)
    await audit.record(
        session,
        AuditAction.SUMMARY_APPROVED,
        "summary",
        summary.id,
        actor=actor,
        model=summary.model,
        prompt_version=summary.prompt_version,
        schema_version=summary.schema_version,
        details={
            "edit_ratio": summary.diff["edit_ratio"],
            "fields_changed": len(summary.diff["changed_fields"]),
        },
    )
    return summary


async def reject_summary(
    session: AsyncSession, actor: Principal, note_id: uuid.UUID, reason: str
) -> Summary:
    note = await get_owned_note(session, actor, note_id, for_update=True)
    summary = _require_summary(note)
    note.status = ensure_transition(NoteStatus(note.status), NoteStatus.REJECTED).value
    summary.rejection_reason = reason
    summary.reviewed_by = actor.user_id
    summary.reviewed_at = datetime.now(UTC)
    await audit.record(
        session,
        AuditAction.SUMMARY_REJECTED,
        "summary",
        summary.id,
        actor=actor,
        model=summary.model,
        prompt_version=summary.prompt_version,
        schema_version=summary.schema_version,
        details={"reason_chars": len(reason)},
    )
    return summary


async def request_regeneration(session: AsyncSession, actor: Principal, note_id: uuid.UUID) -> Note:
    """Also serves as retry for FAILED_VALIDATION. Earlier generations are kept for the record."""
    note = await get_owned_note(session, actor, note_id, for_update=True)
    note.status = ensure_transition(NoteStatus(note.status), NoteStatus.SUBMITTED).value
    note.generation += 1
    note.failure_reason = None
    enqueue_note_submitted(session, note, regeneration=True)
    await audit.record(
        session,
        AuditAction.REGENERATION_REQUESTED,
        "note",
        note.id,
        actor=actor,
        details={"generation": note.generation},
    )
    return note
