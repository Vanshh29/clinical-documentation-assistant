"""Outbox relay -> Redpanda -> consumer -> pipeline, against a real broker.

Uses KAFKA_BOOTSTRAP_SERVERS (e.g. `make up` Redpanda on localhost:19092) or starts a container.
"""

import asyncio
import contextlib
import os
import uuid
from collections.abc import Iterator

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from cda_api.adapters.crypto import MappingCipher
from cda_api.adapters.db.models import Note, OutboxEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cda_worker.adapters.fake_provider import FakeProvider
from cda_worker.adapters.kafka import relay_outbox_once, run_consumer
from cda_worker.adapters.redactor import PresidioRedactor
from tests.test_service import BODY, make_note, make_processor


@pytest.fixture(scope="module")
def bootstrap() -> Iterator[str]:
    url = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
    if url:
        yield url
        return
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
    from testcontainers.kafka import RedpandaContainer

    with RedpandaContainer("docker.redpanda.com/redpandadata/redpanda:v24.2.7") as broker:
        yield broker.get_bootstrap_server()


async def test_submitted_note_flows_through_kafka_to_pending_review(
    bootstrap: str,
    session_factory: async_sessionmaker[AsyncSession],
    redactor: PresidioRedactor,
    cipher: MappingCipher,
) -> None:
    note, _ = await make_note(session_factory, BODY)
    proc = make_processor(session_factory, redactor, cipher, FakeProvider())

    producer = AIOKafkaProducer(bootstrap_servers=bootstrap)
    consumer = AIOKafkaConsumer(
        "note.submitted",
        bootstrap_servers=bootstrap,
        group_id=f"test-{uuid.uuid4().hex[:8]}",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    await producer.start()
    await consumer.start()
    task = asyncio.create_task(run_consumer(consumer, proc.process))
    try:
        assert await relay_outbox_once(session_factory, producer) >= 1
        for _ in range(100):
            async with session_factory() as s:
                row = await s.get(Note, note.id)
                if row and row.status == "PENDING_REVIEW":
                    break
            await asyncio.sleep(0.2)
        else:
            pytest.fail("note did not reach PENDING_REVIEW through Kafka")
        # the relay marks rows published, so a second pass sends nothing for this note
        async with session_factory() as s:
            pending = (
                (
                    await s.execute(
                        select(OutboxEvent).where(
                            OutboxEvent.key == str(note.id), OutboxEvent.published_at.is_(None)
                        )
                    )
                )
                .scalars()
                .all()
            )
        # summary.ready was created by the pipeline after the first relay pass
        assert [e.topic for e in pending] == ["summary.ready"]
        assert await relay_outbox_once(session_factory, producer) >= 1
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await consumer.stop()
        await producer.stop()
