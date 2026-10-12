"""Processing of one note: the use case behind a `note.submitted` event."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass

from cda_api.adapters.crypto import MappingCipher
from cda_api.adapters.db.models import Note, PiiMapping
from cda_api.application import processing
from cda_api.domain.enums import NoteStatus
from cda_api.domain.redaction_map import RedactionMap
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cda_worker import metrics
from cda_worker.domain.generation import GenerationOutcome, generate_validated
from cda_worker.domain.limits import truncate_to_budget
from cda_worker.domain.ports import LLMProvider, Redactor
from cda_worker.domain.prompts import PromptBuilder

log = logging.getLogger("cda.worker.service")

FAILURE_INTERNAL = "internal_error"
FAILURE_STUCK = "worker_timeout"


@dataclass
class NoteProcessor:
    session_factory: async_sessionmaker[AsyncSession]
    redactor: Redactor
    cipher: MappingCipher
    provider: LLMProvider
    prompts: PromptBuilder
    max_input_tokens: int
    max_validation_retries: int
    model_name: str

    async def process(self, note_id: uuid.UUID, generation: int) -> str:
        """Returns 'done', 'failed' or 'skipped'. Safe to call twice for the same event."""
        started = time.perf_counter()
        claimed = await self._claim(note_id, generation)
        if claimed is None:
            metrics.NOTES.labels("skipped").inc()
            return "skipped"  # duplicate delivery, regenerated since, or erased
        body, language = claimed

        redaction = await asyncio.to_thread(self.redactor.redact, body, language)
        await self._store_mapping(note_id, redaction.mapping)
        text, truncated = truncate_to_budget(redaction.text, self.max_input_tokens)

        outcome = await generate_validated(
            self.provider,
            self.prompts,
            text,
            max_validation_retries=self.max_validation_retries,
            model_name=self.model_name,
        )
        await self._finish(note_id, outcome)
        self._record(outcome, redaction.counts, time.perf_counter() - started)
        log.info(
            "note processed",
            extra={
                "ctx": {
                    "note_id": str(note_id),
                    "outcome": "ok" if outcome.summary else outcome.failure_reason,
                    "model": outcome.model,
                    "prompt_version": outcome.prompt_version,
                    "input_tokens": outcome.input_tokens,
                    "output_tokens": outcome.output_tokens,
                    "latency_ms": outcome.latency_ms,
                    "retries": outcome.retries,
                    "cost_usd": str(outcome.cost_usd),
                    "redactions": redaction.counts,
                    "truncated": truncated,
                }
            },
        )
        return "done" if outcome.summary else "failed"

    @staticmethod
    def _record(outcome: GenerationOutcome, redactions: dict[str, int], seconds: float) -> None:
        metrics.NOTES.labels("ok" if outcome.summary else outcome.failure_reason or "failed").inc()
        metrics.DURATION.observe(seconds)
        metrics.LLM_TOKENS.labels("input").inc(outcome.input_tokens)
        metrics.LLM_TOKENS.labels("output").inc(outcome.output_tokens)
        metrics.LLM_COST.inc(float(outcome.cost_usd))
        metrics.LLM_RETRIES.inc(outcome.retries)
        for kind, n in redactions.items():
            metrics.REDACTIONS.labels(kind).inc(n)

    async def _claim(self, note_id: uuid.UUID, generation: int) -> tuple[str, str] | None:
        async with self.session_factory() as session:
            note = (
                await session.execute(select(Note).where(Note.id == note_id).with_for_update())
            ).scalar_one_or_none()
            if (
                note is None
                or note.status != NoteStatus.SUBMITTED.value
                or note.generation != generation
            ):
                return None
            await processing.start_processing(session, note_id)
            await session.commit()
            return note.body, note.language

    async def _store_mapping(self, note_id: uuid.UUID, mapping: RedactionMap) -> None:
        ciphertext = self.cipher.encrypt(mapping)
        async with self.session_factory() as session:
            row = await session.get(PiiMapping, note_id)
            if row is None:
                session.add(PiiMapping(note_id=note_id, ciphertext=ciphertext))
            else:
                row.ciphertext = ciphertext
            await session.commit()

    async def _finish(self, note_id: uuid.UUID, outcome: GenerationOutcome) -> None:
        async with self.session_factory() as session:
            if outcome.summary is not None:
                await processing.complete_processing(
                    session,
                    note_id,
                    outcome.summary,
                    model=outcome.model,
                    prompt_version=outcome.prompt_version,
                    input_tokens=outcome.input_tokens,
                    output_tokens=outcome.output_tokens,
                    latency_ms=outcome.latency_ms,
                    retries=outcome.retries,
                    cost_usd=outcome.cost_usd,
                )
            else:
                await processing.fail_processing(
                    session,
                    note_id,
                    outcome.failure_reason or FAILURE_INTERNAL,
                    model=outcome.model,
                    prompt_version=outcome.prompt_version,
                    retries=outcome.retries,
                )
            await session.commit()

    async def fail_unexpected(self, note_id: uuid.UUID, reason: str = FAILURE_INTERNAL) -> None:
        """Last resort for infrastructure errors, so a note never sits in PROCESSING forever."""
        async with self.session_factory() as session:
            note = await session.get(Note, note_id)
            if note is None or note.status != NoteStatus.PROCESSING.value:
                return
            await processing.fail_processing(
                session,
                note_id,
                reason,
                model=self.model_name,
                prompt_version=self.prompts.version,
                retries=0,
            )
            await session.commit()
