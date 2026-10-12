import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from cda_api.adapters.crypto import MappingCipher
from cda_api.adapters.db.models import AuditLog, LlmCall, Note, OutboxEvent, PiiMapping, User
from cda_api.application import notes as notes_svc
from cda_api.application import review
from cda_api.domain.enums import Role
from cda_api.domain.principal import Principal
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cda_worker.adapters.fake_provider import FakeProvider
from cda_worker.adapters.redactor import PresidioRedactor
from cda_worker.domain.ports import LLMResult, Prompt
from cda_worker.domain.prompts import PromptBuilder
from cda_worker.main import reap_stuck
from cda_worker.service import NoteProcessor

BODY = (
    "Anna Schmidt (DOB: 03.04.1961) presents with cough for three days. "
    "Takes ibuprofen 400 mg twice daily. No known allergies. Plan: rest and fluids. "
    "Follow-up in two weeks. Call +49 170 1234567."
)


class Spy:
    name = "spy"

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.seen: list[str] = []

    async def generate_structured(
        self, prompt: Prompt, schema: type[BaseModel], **opts: Any
    ) -> LLMResult:
        self.seen.append(prompt.system + "".join(m.content for m in prompt.messages))
        return await self.inner.generate_structured(prompt, schema, **opts)


class Garbage:
    name = "garbage"

    async def generate_structured(self, prompt: Prompt, schema: Any, **opts: Any) -> LLMResult:
        return LLMResult({"nope": 1}, "garbage-1", 10, 5, 1)


def make_processor(
    factory: async_sessionmaker[AsyncSession],
    redactor: PresidioRedactor,
    cipher: MappingCipher,
    provider: Any,
    **kw: Any,
) -> NoteProcessor:
    return NoteProcessor(
        session_factory=factory,
        redactor=redactor,
        cipher=cipher,
        provider=provider,
        prompts=PromptBuilder("v1"),
        max_input_tokens=kw.get("max_input_tokens", 8000),
        max_validation_retries=kw.get("retries", 1),
        model_name="fake",
    )


async def make_note(
    factory: async_sessionmaker[AsyncSession], body: str = BODY
) -> tuple[Note, Principal]:
    async with factory() as s:
        user = User(
            email=f"c-{uuid.uuid4().hex[:8]}@test.example",
            display_name="T",
            role="clinician",
            password_hash="x",
        )
        s.add(user)
        await s.flush()
        actor = Principal(user.id, Role.CLINICIAN, user.email)
        note = await notes_svc.submit_note(
            s, actor, body=body, title=None, language="en", source="paste"
        )
        await s.commit()
        return note, actor


async def test_end_to_end_pending_review_with_encrypted_mapping(
    session_factory: async_sessionmaker[AsyncSession],
    redactor: PresidioRedactor,
    cipher: MappingCipher,
) -> None:
    note, actor = await make_note(session_factory)
    spy = Spy(FakeProvider())
    proc = make_processor(session_factory, redactor, cipher, spy)

    assert await proc.process(note.id, 1) == "done"

    # 1. the model never saw personal data
    sent = "".join(spy.seen)
    assert "Anna Schmidt" not in sent and "03.04.1961" not in sent and "1234567" not in sent
    assert "[PERSON_1]" in sent

    async with session_factory() as s:
        row = (await s.execute(select(Note).where(Note.id == note.id))).scalar_one()
        assert row.status == "PENDING_REVIEW"
        mapping = await s.get(PiiMapping, note.id)
        assert mapping is not None
        # 2. the mapping is encrypted at rest
        assert b"Schmidt" not in mapping.ciphertext
        assert cipher.decrypt(mapping.ciphertext).rehydrate_text("[PERSON_1]") == "Anna Schmidt"
        # 3. stored summary keeps placeholders, display form restores real values
        full = (await s.execute(select(Note).where(Note.id == note.id))).scalar_one()
        await s.refresh(full, ["summaries"])
        summary = full.summaries[-1]
        assert "Schmidt" not in json.dumps(summary.content)
        shown = review.display_content(
            summary, full, await review.load_redaction_map(s, note.id, cipher)
        )
        assert "Anna Schmidt" in json.dumps(shown, ensure_ascii=False)
        for field in ("chief_complaint", "plan"):
            for span in shown[field]["source_spans"]:
                assert BODY[span["start"] : span["end"]] == span["text"]
        # 4. metrics, outbox event and audit trail
        call = (await s.execute(select(LlmCall).where(LlmCall.note_id == note.id))).scalar_one()
        assert call.outcome == "ok" and call.input_tokens > 0
        events = (
            (await s.execute(select(OutboxEvent).where(OutboxEvent.key == str(note.id))))
            .scalars()
            .all()
        )
        assert {e.topic for e in events} == {"note.submitted", "summary.ready"}
        actions = (
            (
                await s.execute(
                    select(AuditLog.action).where(AuditLog.entity_id.in_([note.id, summary.id]))
                )
            )
            .scalars()
            .all()
        )
        assert {"processing.started", "summary.generated"} <= set(actions)


async def test_unedited_approval_has_zero_edit_ratio_despite_placeholders(
    session_factory: async_sessionmaker[AsyncSession],
    redactor: PresidioRedactor,
    cipher: MappingCipher,
) -> None:
    note, actor = await make_note(session_factory)
    await make_processor(session_factory, redactor, cipher, FakeProvider()).process(note.id, 1)
    async with session_factory() as s:
        approved = await review.approve_summary(s, actor, note.id, cipher)
        await s.commit()
    assert approved.diff == {"changed_fields": {}, "edit_ratio": 0.0}
    assert "Anna Schmidt" in json.dumps(approved.approved_content, ensure_ascii=False)


async def test_duplicate_and_stale_events_are_skipped(
    session_factory: async_sessionmaker[AsyncSession],
    redactor: PresidioRedactor,
    cipher: MappingCipher,
) -> None:
    note, _ = await make_note(session_factory)
    proc = make_processor(session_factory, redactor, cipher, FakeProvider())
    assert await proc.process(note.id, 2) == "skipped"  # wrong generation
    assert await proc.process(note.id, 1) == "done"
    assert await proc.process(note.id, 1) == "skipped"  # redelivered event
    assert await proc.process(uuid.uuid4(), 1) == "skipped"  # erased note


async def test_invalid_model_output_ends_in_failed_validation(
    session_factory: async_sessionmaker[AsyncSession],
    redactor: PresidioRedactor,
    cipher: MappingCipher,
) -> None:
    note, _ = await make_note(session_factory)
    assert (
        await make_processor(session_factory, redactor, cipher, Garbage()).process(note.id, 1)
        == "failed"
    )
    async with session_factory() as s:
        row = await s.get(Note, note.id)
        assert row is not None
        assert (row.status, row.failure_reason) == ("FAILED_VALIDATION", "schema_validation_failed")
        call = (await s.execute(select(LlmCall).where(LlmCall.note_id == note.id))).scalar_one()
        assert call.outcome == "failed_validation" and call.retries == 1


async def test_long_note_is_truncated_not_rejected(
    session_factory: async_sessionmaker[AsyncSession],
    redactor: PresidioRedactor,
    cipher: MappingCipher,
) -> None:
    body = "Patient presents with cough for three days. " + "Routine remark here. " * 2000
    note, _ = await make_note(session_factory, body)
    spy = Spy(FakeProvider())
    proc = make_processor(session_factory, redactor, cipher, spy, max_input_tokens=1500)
    assert await proc.process(note.id, 1) == "done"
    assert len(spy.seen[0]) < len(body)


async def test_reaper_fails_notes_stuck_in_processing(
    session_factory: async_sessionmaker[AsyncSession],
    redactor: PresidioRedactor,
    cipher: MappingCipher,
) -> None:
    note, _ = await make_note(session_factory)
    async with session_factory() as s:
        await s.execute(
            update(Note)
            .where(Note.id == note.id)
            .values(status="PROCESSING", updated_at=datetime.now(UTC) - timedelta(hours=1))
        )
        await s.commit()
    proc = make_processor(session_factory, redactor, cipher, FakeProvider())
    await reap_stuck(proc, timedelta(minutes=10))
    async with session_factory() as s:
        row = await s.get(Note, note.id)
        assert row is not None and (row.status, row.failure_reason) == (
            "FAILED_VALIDATION",
            "worker_timeout",
        )


async def test_erasing_data_removes_the_mapping(
    session_factory: async_sessionmaker[AsyncSession],
    redactor: PresidioRedactor,
    cipher: MappingCipher,
) -> None:
    note, actor = await make_note(session_factory)
    await make_processor(session_factory, redactor, cipher, FakeProvider()).process(note.id, 1)
    async with session_factory() as s:
        assert await notes_svc.erase_my_data(s, actor) == 1
        await s.commit()
        assert await s.get(PiiMapping, note.id) is None
        assert (await s.execute(select(LlmCall).where(LlmCall.note_id == note.id))).first() is None


async def test_processing_updates_prometheus_metrics(
    session_factory: async_sessionmaker[AsyncSession],
    redactor: PresidioRedactor,
    cipher: MappingCipher,
) -> None:
    from prometheus_client import REGISTRY

    def val(name: str, labels: dict[str, str] | None = None) -> float:
        return REGISTRY.get_sample_value(name, labels or {}) or 0.0

    ok_before = val("cda_worker_notes_total", {"outcome": "ok"})
    tokens_before = val("cda_worker_llm_tokens_total", {"direction": "input"})
    redacted_before = val("cda_worker_redactions_total", {"type": "PERSON"})
    note, _ = await make_note(session_factory)
    proc = make_processor(session_factory, redactor, cipher, FakeProvider())
    await proc.process(note.id, 1)
    await proc.process(note.id, 1)  # duplicate delivery
    assert val("cda_worker_notes_total", {"outcome": "ok"}) == ok_before + 1
    assert val("cda_worker_notes_total", {"outcome": "skipped"}) >= 1
    assert val("cda_worker_llm_tokens_total", {"direction": "input"}) > tokens_before
    assert val("cda_worker_redactions_total", {"type": "PERSON"}) > redacted_before
    assert val("cda_worker_note_duration_seconds_count") >= 1


async def test_reaper_survives_a_failing_pass_so_the_heartbeat_keeps_running(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import asyncio

    from cda_worker import main as worker_main

    calls = {"n": 0}

    async def flaky(processor: object, older_than: object) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionRefusedError("database starting")

    monkeypatch.setattr(worker_main, "reap_stuck", flaky)
    task = asyncio.create_task(
        worker_main.run_reaper(object(), timedelta(minutes=1), interval=0.01)
    )  # type: ignore[arg-type]
    await asyncio.sleep(0.15)
    assert not task.done()  # a crashed reaper would stop the heartbeat and restart the pod
    assert calls["n"] >= 2
    task.cancel()
