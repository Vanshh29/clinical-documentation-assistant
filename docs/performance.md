# Performance

Measured with `scripts/load_test.py` against the full stack from `make up`. Reproduce:
```bash
make up
apps/api/.venv/bin/python scripts/load_test.py --notes 200 --concurrency 20
```

**Environment:** one Apple M4 laptop, Docker Desktop (10 CPUs, 8 GB), one API container (limit 1 CPU), **one worker** (limit 2 CPU), Postgres and Redpanda single-node, **offline provider**. Each note goes through submit, outbox relay, Kafka, redaction, the provider, validation and storage.

| Run (200 notes) | Reached review | Failed | Wall time | Throughput | Submit p50 / p95 | Submit to review p50 / p95 / max |
|---|---|---|---|---|---|---|
| 5 at a time | 200 | 0 | 20.7 s | 9.7 notes/s | 6 / 11 ms | 0.53 / 0.59 / 0.62 s |
| 20 at a time | 200 | 0 | 5.1 s | 39.0 notes/s | 6 / 58 ms | 0.53 / 0.65 / 0.67 s |

## How to read this
- **Time to review has a floor of about half a second.** The outbox relay polls every 0.5 s (`OUTBOX_POLL_SECONDS`), so that interval, not the pipeline, dominates. Lowering it trades database polling for latency.
- **Throughput here is limited by the load generator's concurrency**, not by the system: latency stayed flat while concurrency quadrupled, and the worker was nearly idle (about 1 % CPU) because the offline provider returns in about a millisecond.
- **A real model changes everything.** Model latency will dominate (seconds, not milliseconds), so throughput per worker will fall to roughly the number of notes the provider can handle concurrently. Scale with more worker replicas, up to the topic's partition count.
- **Redaction cost:** the spaCy models make the worker the heaviest container (about 0.3 GB resident at idle in this run, image 883 MB).
- Single laptop, single run per row, no warm-up control: use the numbers to compare changes on the same machine, not as capacity claims.
