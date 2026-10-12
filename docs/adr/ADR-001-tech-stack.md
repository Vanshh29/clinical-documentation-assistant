# ADR-001: Technology stack

- Status: Accepted
- Date: 2026-10-12

## Context
The project is a clinical documentation assistant: free-text notes become structured, human-reviewed summaries via an asynchronous PII-redacting LLM pipeline. It must be reliable, auditable, GDPR-conscious and cloud-native.

## Decision
| Layer | Choice | Why |
|---|---|---|
| Frontend | React 18, TypeScript (strict), Vite, TanStack Query, React Hook Form + Zod, Tailwind | Mainstream, typed, fast feedback; server state handled by TanStack Query |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic | Pydantic doubles as LLM output validation and API contract |
| Database | PostgreSQL 16 | Transactional workflow state, append-only audit table, JSONB for summaries |
| Messaging | Kafka API (Redpanda locally) | Decouples intake from slow LLM processing; replayable |
| LLM | Anthropic behind an `LLMProvider` port, plus `FakeProvider` | Vendor isolation; offline demo and deterministic tests |
| PII | Presidio (DE + EN) + custom German regex recognizers | Redaction happens before any LLM call |
| Infra | Docker, Compose, Terraform, Helm, ArgoCD, GitHub Actions | GitOps delivery |
| Observability | JSON logs, OpenTelemetry, Prometheus | Standard triad |

Backend uses ports-and-adapters: the domain layer imports no FastAPI, Kafka or LLM SDK.

## Consequences
- Two languages (Python, TypeScript); shared contracts are generated from Pydantic into `packages/schemas`.
- Presidio models add image size to the worker; mitigated by multi-stage builds.
