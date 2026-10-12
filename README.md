# Clinical Documentation Assistant

> **Demo only. Not a medical device. Not for real patient data.** All sample data in this repository is synthetic.

An AI-native, full-stack web app that turns free-text clinical notes into structured, reviewable summaries. A human clinician must review and approve every summary before it is final.

## Status
Done: foundation, domain/API, processing pipeline (Kafka, PII redaction, LLM provider abstraction) and the web app. Evaluation harness and cloud delivery follow.

## Quickstart
```bash
make env && make up                       # .env with a fresh encryption key; Postgres 16 + Redpanda
cd apps/api    && make install && make migrate && make seed
cd ../worker   && make install            # also downloads the spaCy models
# three terminals:
cd apps/api    && make run                # http://localhost:8000/docs
cd apps/worker && make run                # consumes note.submitted, produces summaries
cd apps/web    && npm ci && npm run dev   # http://localhost:5173
```
Runs fully offline with `LLM_PROVIDER=fake` (default, no API key). Set `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY` and `LLM_MODEL` in `.env` to use a real model.

Demo logins: `clinician1@demo.example`, `clinician2@demo.example`, `admin@demo.example`, password `demo-password-123` (local demo only).

Tests: `make test` in `apps/api` and `apps/worker` (real Postgres, and Redpanda for the Kafka flow, via Testcontainers or `TEST_DATABASE_URL` / `KAFKA_BOOTSTRAP_SERVERS`).

## The review screen
![Review screen, light theme](docs/screenshots/review-light.png)

Original note on the left, editable summary on the right. Selecting a field highlights the text that supports it; every field shows a confidence level and says plainly when something is not documented. Nothing is final until a clinician approves it. Dark theme and phone layouts: [`dark`](docs/screenshots/review-dark.png), [`mobile`](docs/screenshots/review-mobile.png). Design decisions: [`ADR-005`](docs/adr/ADR-005-frontend-design.md).

Tests: `npm run test:coverage` (Vitest + Testing Library) and `npm run e2e` (Playwright; needs the stack above running).

## How a note is processed
`POST /notes` -> note + outbox event saved in one transaction -> relay publishes `note.submitted` -> worker redacts PII (typed placeholders, map stored encrypted) -> LLM returns a structured summary with verbatim quotes -> pipeline validates, locates quotes, retries with the error fed back -> `PENDING_REVIEW`. Real values are restored only when the clinician opens the note. Details: [`docs/adr/ADR-004-pipeline-design.md`](docs/adr/ADR-004-pipeline-design.md).

## Measured so far
- PII redaction on a small synthetic DE/EN corpus: see [`docs/pii-redaction-report.md`](docs/pii-redaction-report.md) (baseline vs. with a clinical-term guard; the corpus is small and was used while building the guard, so treat the figures as a regression gate).

## Repository layout
```
apps/web        React frontend
apps/api        FastAPI service
apps/worker     Kafka consumer (PII + LLM pipeline)
packages/schemas  Shared schemas
infra/          Terraform, Helm, ArgoCD
docs/           ADRs, architecture, threat model, eval report
eval/           Evaluation dataset and runner
```

Architecture decisions: [`docs/adr/`](docs/adr/).
