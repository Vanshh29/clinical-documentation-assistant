"""Data retention: hard-delete notes older than the configured TTL (GDPR storage limitation).

Summaries, redaction mappings and call metrics cascade. The audit log keeps only a count.
Run daily: `python -m cda_api.retention` (a Kubernetes CronJob does this).
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from cda_api.adapters.db.models import Note
from cda_api.adapters.db.session import make_engine, make_session_factory
from cda_api.application import audit
from cda_api.config import get_settings
from cda_api.domain.enums import AuditAction

log = logging.getLogger("cda.retention")


async def purge_expired(
    session: AsyncSession, retention_days: int, *, now: datetime | None = None
) -> int:
    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    result = await session.execute(delete(Note).where(Note.created_at < cutoff))
    count = int(result.rowcount or 0)  # type: ignore[attr-defined]
    await audit.record(
        session,
        AuditAction.RETENTION_PURGE,
        "system",
        None,
        details={"notes_deleted": count, "retention_days": retention_days},
    )
    return count


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        count = await purge_expired(session, settings.retention_days)
        await session.commit()
    await engine.dispose()
    print(f"retention purge removed {count} note(s) older than {settings.retention_days} days")


if __name__ == "__main__":
    asyncio.run(main())
