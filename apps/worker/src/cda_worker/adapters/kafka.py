import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from cda_api.adapters.db.models import OutboxEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = logging.getLogger("cda.worker.kafka")


async def relay_outbox_once(
    session_factory: async_sessionmaker[AsyncSession],
    producer: AIOKafkaProducer,
    batch_size: int = 100,
) -> int:
    """Publish pending outbox rows. At-least-once: consumers are idempotent (see NoteProcessor).

    SKIP LOCKED lets several relays run side by side without double-sending.
    """
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.published_at.is_(None))
                    .order_by(OutboxEvent.created_at)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            await producer.send_and_wait(
                row.topic, json.dumps(row.payload).encode(), key=row.key.encode()
            )
            row.published_at = datetime.now(UTC)
        await session.commit()
        return len(rows)


async def run_relay(
    session_factory: async_sessionmaker[AsyncSession],
    producer: AIOKafkaProducer,
    poll_seconds: float,
) -> None:
    while True:
        try:
            sent = await relay_outbox_once(session_factory, producer)
        except Exception:
            log.exception("outbox relay failed; will retry")
            sent = 0
        if sent == 0:
            await asyncio.sleep(poll_seconds)


Handler = Callable[[uuid.UUID, int], Awaitable[None]]


async def run_consumer(
    consumer: AIOKafkaConsumer, handler: Handler, *, max_attempts: int = 3
) -> None:
    """Commit an offset only after the message is fully handled (at-least-once)."""
    async for message in consumer:
        try:
            payload = json.loads(message.value or b"{}")
            note_id, generation = uuid.UUID(payload["note_id"]), int(payload["generation"])
        except (ValueError, KeyError, TypeError):
            log.error("dropping malformed event", extra={"ctx": {"offset": message.offset}})
            await consumer.commit()
            continue
        for attempt in range(1, max_attempts + 1):
            try:
                await handler(note_id, generation)
                break
            except Exception:
                log.exception(
                    "handler failed", extra={"ctx": {"note_id": str(note_id), "attempt": attempt}}
                )
                await asyncio.sleep(min(2**attempt, 10))
        await consumer.commit()
