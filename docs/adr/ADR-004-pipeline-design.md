# ADR-004: Processing pipeline design

- Status: Accepted
- Date: 2026-10-12

## Decisions
1. **Redact before any LLM call.** Presidio (spaCy NER for names and places) plus regex recognizers for German and international formats: insurance number (KVNR), phone, IBAN, e-mail, dates and dates of birth. Clinical durations ("seit drei Tagen") are not redacted, as they carry the clinical meaning.
2. **Typed placeholders, encrypted map.** `[PERSON_1]`, `[DOB_1]`... The same text always gets the same placeholder. The map (placeholder, original, offsets in both texts) is Fernet-encrypted in `pii_mappings`, apart from the LLM payload.
3. **Stored summaries keep placeholders.** The API restores real values and translates source-span offsets to the original text only when a clinician opens the note. Approval diffs are computed in display form so placeholder substitution never counts as a clinician edit.
4. **The model quotes, the pipeline locates.** Models are unreliable at counting characters, so the LLM returns verbatim quotes. The pipeline finds each quote in the redacted note and computes offsets; a quote that is not found verbatim is rejected and fed back. A second post-check confirms every stored span matches the text.
5. **Bounded retries with the error fed back.** Invalid output is re-asked up to `LLM_MAX_VALIDATION_RETRIES` times, then the note becomes `FAILED_VALIDATION` with a machine-readable reason (`schema_validation_failed`, `llm_unavailable`, `llm_request_rejected`, `worker_timeout`).
6. **Transport resilience.** Exponential backoff with full jitter on 429/5xx and timeouts (honouring `Retry-After`), then a circuit breaker so an outage fails fast instead of stalling the queue.
7. **Input limit.** Tokens are estimated at 4 characters each. Over-long notes are cut at the last sentence boundary within budget; a prefix keeps span offsets valid.
8. **Delivery.** Transactional outbox -> relay -> Kafka (`SKIP LOCKED`, at-least-once). The consumer commits offsets after handling and the processor is idempotent (state and generation checks), so redelivery is harmless. A reaper fails notes left in `PROCESSING` by a crashed worker.
9. **Provider.** `OpenRouterProvider` and an offline `FakeProvider` sit behind one `LLMProvider` port. Further providers can be added without touching the pipeline.

## Known trade-offs
- The worker imports the API package for models and state transitions. This avoids duplicating the schema, at the cost of coupled releases; extracting a shared `cda-core` package is the next step if the services diverge.
- spaCy *small* models are fast but weak at German names; the clinical-term guard compensates for known failure modes and is measured in `docs/pii-redaction-report.md`.
