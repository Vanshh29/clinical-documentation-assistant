import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import FastAPI
from prometheus_client import REGISTRY
from sqlalchemy import select, update

from cda_api.adapters.db.models import AuditLog, Note, PiiMapping
from cda_api.observability import route_label, setup_tracing
from cda_api.retention import purge_expired
from tests.conftest import Account
from tests.factories import NOTE_TEXT


def sample(name: str, labels: dict[str, str]) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


async def test_requests_are_counted_by_route_template_not_raw_path(
    client: httpx.AsyncClient, make_account
) -> None:  # type: ignore[no-untyped-def]
    acct: Account = await make_account()
    labels = {"method": "GET", "route": "/notes/{note_id}", "status": "404"}
    before = sample("cda_http_requests_total", labels)
    for _ in range(3):  # three different ids, one label set
        await client.get(f"/notes/{uuid.uuid4()}", headers=acct.headers)
    assert sample("cda_http_requests_total", labels) == before + 3
    assert (
        sample(
            "cda_http_request_duration_seconds_count",
            {"method": "GET", "route": "/notes/{note_id}"},
        )
        >= 3
    )


async def test_health_probes_do_not_pollute_metrics(client: httpx.AsyncClient) -> None:
    before = sample(
        "cda_http_requests_total", {"method": "GET", "route": "/healthz", "status": "200"}
    )
    await client.get("/healthz")
    assert (
        sample("cda_http_requests_total", {"method": "GET", "route": "/healthz", "status": "200"})
        == before
    )


def test_unmatched_routes_share_one_label(app: FastAPI) -> None:
    class Req:
        scope: dict[str, object] = {}

    assert route_label(Req()) == "unmatched"  # type: ignore[arg-type]


def test_tracing_is_off_without_an_endpoint_and_on_with_one() -> None:
    assert setup_tracing(None, "", "cda-test") is False
    assert setup_tracing(None, "http://localhost:4318", "cda-test") is True


async def _note(session_factory, owner: Account, age_days: int) -> uuid.UUID:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        note = Note(owner_id=owner.id, body=NOTE_TEXT, status="PENDING_REVIEW")
        s.add(note)
        await s.flush()
        s.add(PiiMapping(note_id=note.id, ciphertext=b"x"))
        await s.execute(
            update(Note)
            .where(Note.id == note.id)
            .values(created_at=datetime.now(UTC) - timedelta(days=age_days))
        )
        await s.commit()
        return note.id


async def test_retention_deletes_only_expired_notes_with_their_mappings(
    session_factory, make_account
) -> None:  # type: ignore[no-untyped-def]
    owner = await make_account()
    old, fresh = await _note(session_factory, owner, 45), await _note(session_factory, owner, 2)
    async with session_factory() as s:
        deleted = await purge_expired(s, retention_days=30)
        await s.commit()
    assert deleted >= 1
    async with session_factory() as s:
        assert await s.get(Note, old) is None
        assert await s.get(PiiMapping, old) is None  # cascades
        assert await s.get(Note, fresh) is not None
        entry = (
            await s.execute(
                select(AuditLog)
                .where(AuditLog.action == "data.retention_purge")
                .order_by(AuditLog.id.desc())
                .limit(1)
            )
        ).scalar_one()
        assert entry.details["retention_days"] == 30
        assert "Synthetic" not in str(entry.details)  # counts only, never content


def test_concurrent_migrations_are_serialized_and_both_succeed(database_url: str) -> None:
    """Several API replicas can start at once; the advisory lock keeps their migrations from colliding."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    import psycopg2

    admin = database_url.replace("postgresql+asyncpg", "postgresql").rsplit("/", 1)[0] + "/postgres"
    name = f"mig_{uuid.uuid4().hex[:8]}"
    conn = psycopg2.connect(admin)
    conn.autocommit = True
    conn.cursor().execute(f'CREATE DATABASE "{name}"')
    target = database_url.rsplit("/", 1)[0] + f"/{name}"
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "DATABASE_URL": target, "PYTHONPATH": str(root / "src")}
    procs = [
        subprocess.Popen([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(4)
    ]  # fmt: skip
    results = [(p.wait(timeout=120), p.stderr.read() if p.stderr else "") for p in procs]
    conn.cursor().execute(f'DROP DATABASE "{name}" WITH (FORCE)')
    conn.close()
    assert all(code == 0 for code, _ in results), results
