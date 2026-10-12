# Clinical Documentation Assistant

> **Demo only. Not a medical device. Not for real patient data.** All sample data in this repository is synthetic.

An AI-native, full-stack web app that turns free-text clinical notes into structured, reviewable summaries. A human clinician must review and approve every summary before it is final.

## Status
Phase 1 (Foundation) in progress.

## Quickstart (infrastructure only, for now)
```bash
cp .env.example .env
make up      # Postgres 16 + Redpanda
make down
```

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
