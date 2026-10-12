# Clinical Documentation Assistant

> **Demo only. Not a medical device. Not for real patient data.** All sample data in this repository is synthetic.

An AI-native, full-stack web app that turns free-text clinical notes into structured, reviewable summaries. A human clinician must review and approve every summary before it is final.

## Status
Phase 1 (foundation) and Phase 2 (domain and API) done. Pipeline, frontend, eval and cloud delivery follow.

## Quickstart (infrastructure only, for now)
```bash
cp .env.example .env
make up      # Postgres 16 + Redpanda
make down

# API (needs make up first)
cd apps/api && make install && make migrate && make seed && make run
make test      # 33 tests, real Postgres via Testcontainers
```

Demo logins after seeding: `clinician1@demo.example`, `clinician2@demo.example`, `admin@demo.example`, password `demo-password-123` (local demo only).

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
