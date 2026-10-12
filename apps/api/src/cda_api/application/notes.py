import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cda_api.adapters.db.models import Note, OutboxEvent
from cda_api.application import audit
from cda_api.domain.enums import AuditAction, NoteStatus, Role
from cda_api.domain.errors import Forbidden, NotFound
from cda_api.domain.principal import Principal

TOPIC_NOTE_SUBMITTED = "note.submitted"


def enqueue_note_submitted(
    session: AsyncSession, note: Note, *, regeneration: bool = False
) -> None:
    """The event carries identifiers only; the worker loads the text itself."""
    session.add(
        OutboxEvent(
            topic=TOPIC_NOTE_SUBMITTED,
            key=str(note.id),
            payload={
                "note_id": str(note.id),
                "generation": note.generation,
                "regeneration": regeneration,
            },
        )
    )


async def submit_note(
    session: AsyncSession,
    actor: Principal,
    *,
    body: str,
    title: str | None,
    language: str,
    source: str,
) -> Note:
    note = Note(
        owner_id=actor.user_id,
        body=body,
        title=title,
        language=language,
        source=source,
        status=NoteStatus.SUBMITTED.value,
    )
    session.add(note)
    await session.flush()
    enqueue_note_submitted(session, note)
    await audit.record(
        session,
        AuditAction.NOTE_SUBMITTED,
        "note",
        note.id,
        actor=actor,
        details={"chars": len(body), "language": language, "source": source},
    )
    return note


async def get_owned_note(
    session: AsyncSession, actor: Principal, note_id: uuid.UUID, *, for_update: bool = False
) -> Note:
    """Clinicians reach only their own notes. Admins get aggregate views, not note text.

    A note owned by someone else is reported as not found so ids cannot be probed.
    """
    if actor.role is not Role.CLINICIAN:
        raise Forbidden("only clinicians can access notes")
    stmt = select(Note).where(Note.id == note_id).options(selectinload(Note.summaries))
    if for_update:
        stmt = stmt.with_for_update(of=Note)  # serialize concurrent review actions
    note = (await session.execute(stmt)).scalar_one_or_none()
    if note is None or note.owner_id != actor.user_id:
        raise NotFound("note not found")
    return note


async def list_notes(
    session: AsyncSession,
    actor: Principal,
    *,
    status: NoteStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[Note], int]:
    if actor.role is not Role.CLINICIAN:
        raise Forbidden("only clinicians can access notes")
    base = select(Note).where(Note.owner_id == actor.user_id)
    if status:
        base = base.where(Note.status == status.value)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await session.execute(base.order_by(Note.created_at.desc()).limit(limit).offset(offset))
    ).scalars()
    return list(rows), total


async def erase_my_data(session: AsyncSession, actor: Principal) -> int:
    """Right to erasure: hard-delete the actor's notes (summaries, mappings, metrics cascade).

    The audit trail keeps only ids and counts, so it stays append-only without holding PII.
    """
    result = await session.execute(delete(Note).where(Note.owner_id == actor.user_id))
    count = int(result.rowcount or 0)  # type: ignore[attr-defined]
    await audit.record(
        session,
        AuditAction.DATA_ERASED,
        "user",
        actor.user_id,
        actor=actor,
        details={"notes_deleted": count},
    )
    return count
