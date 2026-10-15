import asyncio
import contextlib
import logging
import signal
import uuid
from datetime import UTC, datetime, timedelta

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from cda_api.adapters.crypto import MappingCipher
from cda_api.adapters.db.models import Note
from cda_api.adapters.db.session import make_engine, make_session_factory
from cda_api.domain.enums import NoteStatus
from cda_api.logging_setup import configure_logging
from prometheus_client import start_http_server
from sqlalchemy import select

from cda_worker.adapters.circuit_breaker import CircuitBreakerProvider
from cda_worker.adapters.fake_provider import FakeProvider
from cda_worker.adapters.kafka import run_consumer, run_relay
from cda_worker.adapters.openrouter_provider import OpenRouterProvider
from cda_worker.adapters.redactor import PresidioRedactor
from cda_worker.admin_topics import ensure_topics
from cda_worker.domain.ports import LLMProvider
from cda_worker.domain.prompts import PromptBuilder
from cda_worker.health import heartbeat
from cda_worker.service import FAILURE_STUCK, NoteProcessor
from cda_worker.settings import WorkerSettings, get_settings

log = logging.getLogger("cda.worker")


def build_provider(settings: WorkerSettings) -> tuple[LLMProvider, str]:
    if settings.llm_provider == "fake":
        provider: LLMProvider = FakeProvider()
        return provider, FakeProvider.model
    if settings.llm_provider == "openrouter":
        if not settings.llm_model:
            raise SystemExit("LLM_MODEL must be set when LLM_PROVIDER=openrouter")
        inner = OpenRouterProvider(
            settings.openrouter_api_key,
            settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            max_output_tokens=settings.llm_max_output_tokens,
            price_in_per_mtok=settings.llm_price_in_per_mtok,
            price_out_per_mtok=settings.llm_price_out_per_mtok,
        )
        return CircuitBreakerProvider(inner), settings.llm_model
    raise SystemExit(f"unknown LLM_PROVIDER {settings.llm_provider!r}")


async def reap_stuck(processor: NoteProcessor, older_than: timedelta) -> None:
    """Fail notes left in PROCESSING by a crashed worker so they can be retried from the UI."""
    cutoff = datetime.now(UTC) - older_than
    async with processor.session_factory() as session:
        ids = (
            (
                await session.execute(
                    select(Note.id).where(
                        Note.status == NoteStatus.PROCESSING.value, Note.updated_at < cutoff
                    )
                )
            )
            .scalars()
            .all()
        )
    for note_id in ids:
        await processor.fail_unexpected(note_id, FAILURE_STUCK)


async def prepare_topics(settings: WorkerSettings, attempts: int = 10) -> None:
    """Create the topics with enough partitions to scale consumers. Waits for the broker."""
    if settings.kafka_topic_partitions <= 0:
        return
    for attempt in range(1, attempts + 1):
        try:
            created = await ensure_topics(
                settings.kafka_bootstrap_servers,
                settings.kafka_topic_partitions,
                settings.kafka_replication_factor,
            )
            log.info("topics ready", extra={"ctx": {"created": created}})
            return
        except Exception:
            log.warning("broker not ready for topic setup", extra={"ctx": {"attempt": attempt}})
            if attempt == attempts:
                raise
            await asyncio.sleep(min(2**attempt, 15))


async def run_reaper(
    processor: NoteProcessor, older_than: timedelta, interval: float = 60.0
) -> None:
    """Never let a transient database error end this task: its death would stop the heartbeat."""
    while True:
        try:
            await reap_stuck(processor, older_than)
        except Exception:
            log.exception("reaper pass failed; will retry")
        await asyncio.sleep(interval)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logging.getLogger("presidio-analyzer").setLevel(
        logging.ERROR
    )  # unmapped spaCy labels are expected
    engine = make_engine(settings.database_url)
    factory = make_session_factory(engine)
    provider, model_name = build_provider(settings)
    processor = NoteProcessor(
        session_factory=factory,
        redactor=PresidioRedactor(),
        cipher=MappingCipher(settings.pii_encryption_key),
        provider=provider,
        prompts=PromptBuilder(settings.prompt_version),
        max_input_tokens=settings.llm_max_input_tokens,
        max_validation_retries=settings.llm_max_validation_retries,
        model_name=model_name,
    )

    async def handle(note_id: uuid.UUID, generation: int) -> None:
        try:
            await processor.process(note_id, generation)
        except Exception:
            await processor.fail_unexpected(note_id)
            raise

    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    consumer = AIOKafkaConsumer(
        settings.kafka_topic_note_submitted,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    start_http_server(settings.metrics_port)
    await prepare_topics(settings)
    await producer.start()
    await consumer.start()

    tasks = [
        asyncio.create_task(run_relay(factory, producer, settings.outbox_poll_seconds)),
        asyncio.create_task(run_consumer(consumer, handle)),
        asyncio.create_task(run_reaper(processor, timedelta(minutes=settings.stuck_after_minutes))),
    ]
    tasks.append(asyncio.create_task(heartbeat(settings.heartbeat_path, list(tasks))))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    log.info("worker started", extra={"ctx": {"provider": provider.name, "model": model_name}})
    await stop.wait()
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await consumer.stop()
    await producer.stop()
    await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
