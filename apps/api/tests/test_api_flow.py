import uuid
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from cda_api.adapters.db.models import AuditLog, OutboxEvent
from cda_api.application import processing
from cda_api.domain.enums import Role
from tests.conftest import PASSWORD
from tests.factories import NOTE_TEXT, make_summary


async def _submit(client: httpx.AsyncClient, acct) -> dict:  # type: ignore[no-untyped-def]
    r = await client.post("/notes", json={"body": NOTE_TEXT}, headers=acct.headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _generate(session_factory, note_id: str) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        nid = uuid.UUID(note_id)
        await processing.start_processing(s, nid)
        await processing.complete_processing(
            s,
            nid,
            make_summary(),
            model="fake",
            prompt_version="v1",
            input_tokens=100,
            output_tokens=50,
            latency_ms=12,
            retries=0,
            cost_usd=Decimal("0"),
        )
        await s.commit()


async def test_health_endpoints(client: httpx.AsyncClient) -> None:
    assert (await client.get("/healthz")).json() == {"status": "ok"}
    assert (await client.get("/readyz")).status_code == 200


async def test_login_success_and_failure(client, make_account, session_factory) -> None:  # type: ignore[no-untyped-def]
    acct = await make_account()
    ok = await client.post("/auth/token", json={"email": acct.email, "password": PASSWORD})
    assert ok.status_code == 200
    me = await client.get("/me", headers={"Authorization": f"Bearer {ok.json()['access_token']}"})
    assert me.json()["role"] == "clinician"
    bad = await client.post("/auth/token", json={"email": acct.email, "password": "wrong"})
    assert bad.status_code == 401
    unknown = await client.post("/auth/token", json={"email": "nobody@x.example", "password": "x"})
    assert unknown.status_code == 401


async def test_requires_authentication(client: httpx.AsyncClient) -> None:
    assert (await client.get("/notes")).status_code == 401
    r = await client.get("/notes", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


async def test_submit_creates_outbox_event_without_note_text(
    client, make_account, session_factory
) -> None:  # type: ignore[no-untyped-def]
    acct = await make_account()
    note = await _submit(client, acct)
    assert note["status"] == "SUBMITTED"
    async with session_factory() as s:
        event = (
            await s.execute(select(OutboxEvent).where(OutboxEvent.key == note["id"]))
        ).scalar_one()
    assert event.topic == "note.submitted"
    assert "cough" not in str(event.payload)
    assert event.payload["note_id"] == note["id"]


async def test_short_note_rejected(client, make_account) -> None:  # type: ignore[no-untyped-def]
    acct = await make_account()
    r = await client.post("/notes", json={"body": "too short"}, headers=acct.headers)
    assert r.status_code == 422


async def test_full_review_flow_with_diff_and_audit(client, make_account, session_factory) -> None:  # type: ignore[no-untyped-def]
    acct = await make_account()
    note = await _submit(client, acct)
    await _generate(session_factory, note["id"])

    detail = (await client.get(f"/notes/{note['id']}", headers=acct.headers)).json()
    assert detail["status"] == "PENDING_REVIEW"
    assert detail["summary"]["content"]["chief_complaint"]["value"] == "cough for three days"

    edited = make_summary("dry cough for three days").model_dump(mode="json")
    r = await client.put(f"/notes/{note['id']}/summary", json=edited, headers=acct.headers)
    assert r.status_code == 200

    r = await client.post(f"/notes/{note['id']}/approve", headers=acct.headers)
    assert r.status_code == 200
    body = r.json()
    assert body["approved_content"]["chief_complaint"]["value"] == "dry cough for three days"
    assert "chief_complaint" in body["diff"]["changed_fields"]
    assert body["content"]["chief_complaint"]["value"] == "cough for three days"  # original kept

    final = (await client.get(f"/notes/{note['id']}", headers=acct.headers)).json()
    assert final["status"] == "APPROVED"

    async with session_factory() as s:
        actions = (
            (
                await s.execute(
                    select(AuditLog.action)
                    .where(AuditLog.actor_id == acct.id)
                    .order_by(AuditLog.id)
                )
            )
            .scalars()
            .all()
        )
    assert {"note.submitted", "summary.edited", "summary.approved"} <= set(actions)


async def test_audit_entries_contain_no_note_text(client, make_account, session_factory) -> None:  # type: ignore[no-untyped-def]
    acct = await make_account()
    note = await _submit(client, acct)
    await _generate(session_factory, note["id"])
    await client.post(
        f"/notes/{note['id']}/reject", json={"reason": "wrong patient"}, headers=acct.headers
    )
    async with session_factory() as s:
        rows = (
            (await s.execute(select(AuditLog).where(AuditLog.entity_id.is_not(None))))
            .scalars()
            .all()
        )
    assert all("cough" not in str(r.details) for r in rows)
    assert all("wrong patient" not in str(r.details) for r in rows)


async def test_cannot_approve_twice_or_edit_after_approval(
    client, make_account, session_factory
) -> None:  # type: ignore[no-untyped-def]
    acct = await make_account()
    note = await _submit(client, acct)
    await _generate(session_factory, note["id"])
    assert (
        await client.post(f"/notes/{note['id']}/approve", headers=acct.headers)
    ).status_code == 200
    assert (
        await client.post(f"/notes/{note['id']}/approve", headers=acct.headers)
    ).status_code == 409
    edited = make_summary().model_dump(mode="json")
    r = await client.put(f"/notes/{note['id']}/summary", json=edited, headers=acct.headers)
    assert r.status_code == 422


async def test_approve_without_summary_is_not_found(client, make_account) -> None:  # type: ignore[no-untyped-def]
    acct = await make_account()
    note = await _submit(client, acct)
    r = await client.post(f"/notes/{note['id']}/approve", headers=acct.headers)
    assert r.status_code == 404


async def test_regeneration_bumps_generation_and_queues_event(
    client, make_account, session_factory
) -> None:  # type: ignore[no-untyped-def]
    acct = await make_account()
    note = await _submit(client, acct)
    await _generate(session_factory, note["id"])
    r = await client.post(f"/notes/{note['id']}/regenerate", headers=acct.headers)
    assert r.status_code == 202
    assert r.json()["status"] == "SUBMITTED"
    assert r.json()["generation"] == 2
    async with session_factory() as s:
        events = (
            (await s.execute(select(OutboxEvent).where(OutboxEvent.key == note["id"])))
            .scalars()
            .all()
        )
    assert sorted(e.topic for e in events) == ["note.submitted", "note.submitted", "summary.ready"]


async def test_failed_validation_can_be_retried(client, make_account, session_factory) -> None:  # type: ignore[no-untyped-def]
    acct = await make_account()
    note = await _submit(client, acct)
    async with session_factory() as s:
        nid = uuid.UUID(note["id"])
        await processing.start_processing(s, nid)
        await processing.fail_processing(
            s, nid, "schema_validation_failed", model="fake", prompt_version="v1", retries=3
        )
        await s.commit()
    detail = (await client.get(f"/notes/{note['id']}", headers=acct.headers)).json()
    assert detail["status"] == "FAILED_VALIDATION"
    assert detail["failure_reason"] == "schema_validation_failed"
    r = await client.post(f"/notes/{note['id']}/regenerate", headers=acct.headers)
    assert r.status_code == 202


async def test_clinicians_cannot_see_each_others_notes(client, make_account) -> None:  # type: ignore[no-untyped-def]
    owner, other = await make_account(), await make_account()
    note = await _submit(client, owner)
    assert (await client.get(f"/notes/{note['id']}", headers=other.headers)).status_code == 404
    assert (
        await client.post(f"/notes/{note['id']}/approve", headers=other.headers)
    ).status_code == 404
    listing = (await client.get("/notes", headers=other.headers)).json()
    assert listing["total"] == 0


async def test_admin_cannot_read_notes_but_can_read_audit(client, make_account) -> None:  # type: ignore[no-untyped-def]
    clinician, admin = await make_account(), await make_account(Role.ADMIN)
    note = await _submit(client, clinician)
    assert (await client.get(f"/notes/{note['id']}", headers=admin.headers)).status_code == 403
    assert (await client.get("/notes", headers=admin.headers)).status_code == 403
    audit = await client.get("/admin/audit?action=note.submitted", headers=admin.headers)
    assert audit.status_code == 200 and audit.json()["total"] >= 1
    assert (await client.get("/admin/audit", headers=clinician.headers)).status_code == 403


async def test_erasure_deletes_data_and_keeps_audit(client, make_account, session_factory) -> None:  # type: ignore[no-untyped-def]
    acct = await make_account()
    note = await _submit(client, acct)
    await _generate(session_factory, note["id"])
    r = await client.delete("/me/data", headers=acct.headers)
    assert r.json() == {"notes_deleted": 1}
    assert (await client.get(f"/notes/{note['id']}", headers=acct.headers)).status_code == 404
    async with session_factory() as s:
        erased = (
            (
                await s.execute(
                    select(AuditLog).where(
                        AuditLog.actor_id == acct.id, AuditLog.action == "data.erased"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(erased) == 1 and erased[0].details == {"notes_deleted": 1}


async def test_audit_log_is_append_only(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        s.add(AuditLog(action="test.append", entity_type="test", details={}))
        await s.commit()
    async with session_factory() as s:
        with pytest.raises(DBAPIError, match="append-only"):
            await s.execute(text("UPDATE audit_log SET action = 'tampered'"))
    async with session_factory() as s:
        with pytest.raises(DBAPIError, match="append-only"):
            await s.execute(text("DELETE FROM audit_log"))
