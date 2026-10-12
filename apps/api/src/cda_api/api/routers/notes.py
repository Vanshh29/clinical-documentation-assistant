import uuid

from fastapi import APIRouter, Query, status

from cda_api.adapters.db.models import Note
from cda_api.api.deps import ClinicianDep, SessionDep, SettingsDep
from cda_api.api.schemas import (
    ErasureResult,
    NoteCreate,
    NoteDetail,
    NoteList,
    NoteOut,
    RejectRequest,
    SummaryOut,
)
from cda_api.application import notes as notes_svc
from cda_api.application import review
from cda_api.domain.enums import NoteStatus
from cda_api.domain.errors import ValidationFailed
from cda_api.domain.summary_schema import ClinicalSummary

router = APIRouter(tags=["notes"])


def _detail(note: Note) -> NoteDetail:
    base = NoteOut.model_validate(note).model_dump()
    current = review.current_summary(note)
    return NoteDetail(
        **base,
        body=note.body,
        summary=SummaryOut.model_validate(current) if current else None,
    )


@router.post("/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def create_note(
    body: NoteCreate, actor: ClinicianDep, session: SessionDep, settings: SettingsDep
) -> NoteOut:
    if len(body.body) > settings.max_note_chars:
        raise ValidationFailed(f"note exceeds {settings.max_note_chars} characters")
    note = await notes_svc.submit_note(
        session,
        actor,
        body=body.body,
        title=body.title,
        language=body.language,
        source=body.source,
    )
    return NoteOut.model_validate(note)


@router.get("/notes", response_model=NoteList)
async def list_notes(
    actor: ClinicianDep,
    session: SessionDep,
    status_filter: NoteStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> NoteList:
    rows, total = await notes_svc.list_notes(
        session, actor, status=status_filter, limit=limit, offset=offset
    )
    return NoteList(items=[NoteOut.model_validate(n) for n in rows], total=total)


@router.get("/notes/{note_id}", response_model=NoteDetail)
async def get_note(note_id: uuid.UUID, actor: ClinicianDep, session: SessionDep) -> NoteDetail:
    return _detail(await notes_svc.get_owned_note(session, actor, note_id))


@router.put("/notes/{note_id}/summary", response_model=SummaryOut)
async def edit_summary(
    note_id: uuid.UUID, body: ClinicalSummary, actor: ClinicianDep, session: SessionDep
) -> SummaryOut:
    return SummaryOut.model_validate(await review.edit_summary(session, actor, note_id, body))


@router.post("/notes/{note_id}/approve", response_model=SummaryOut)
async def approve(note_id: uuid.UUID, actor: ClinicianDep, session: SessionDep) -> SummaryOut:
    return SummaryOut.model_validate(await review.approve_summary(session, actor, note_id))


@router.post("/notes/{note_id}/reject", response_model=SummaryOut)
async def reject(
    note_id: uuid.UUID, body: RejectRequest, actor: ClinicianDep, session: SessionDep
) -> SummaryOut:
    return SummaryOut.model_validate(
        await review.reject_summary(session, actor, note_id, body.reason)
    )


@router.post("/notes/{note_id}/regenerate", response_model=NoteOut, status_code=202)
async def regenerate(note_id: uuid.UUID, actor: ClinicianDep, session: SessionDep) -> NoteOut:
    return NoteOut.model_validate(await review.request_regeneration(session, actor, note_id))


@router.delete("/me/data", response_model=ErasureResult)
async def erase_my_data(actor: ClinicianDep, session: SessionDep) -> ErasureResult:
    """Right to erasure: removes all of the caller's notes and derived data."""
    return ErasureResult(notes_deleted=await notes_svc.erase_my_data(session, actor))
