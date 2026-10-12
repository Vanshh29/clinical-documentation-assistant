# Clinical Documentation Assistant

> **Demo only. Not a medical device. Not for real patient data.** All sample data in this repository is synthetic.

A full-stack web app that turns free-text clinical notes into structured, reviewable summaries. A human clinician must review and approve every summary before it is final.

## Status
Built and tested: domain and API, processing pipeline (Kafka, PII redaction, model provider abstraction), web app, evaluation harness, container images, Helm chart, Terraform for AWS, ArgoCD apps and CI/CD. See [what is verified and what is not](docs/deploy.md#what-has-and-has-not-been-run).

## Quickstart
Needs Docker. This builds the images and starts everything (Postgres 16, Redpanda, API, worker, web):
```bash
make up                  # creates .env with a fresh encryption key on first run
open http://localhost:8080
make down                # stop; add V=1 to also delete the data volumes
```
Demo logins: `clinician1@demo.example`, `clinician2@demo.example`, `admin@demo.example`, password `demo-password-123` (local demo only).

It runs fully offline with `LLM_PROVIDER=fake` (default, no API key). To use a hosted model set `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY` and `LLM_MODEL` in `.env`, then `make up` again.

### Working on the code
```bash
make infra                                # just Postgres + Redpanda in Docker
cd apps/api    && make install && make migrate && make seed && make run     # http://localhost:8000/docs
cd apps/worker && make install && make run                                  # consumes note.submitted
cd apps/web    && npm ci && npm run dev                                     # http://localhost:5173
```
Tests: `make test` in `apps/api`, `apps/worker` and `eval` (real Postgres and Redpanda through Testcontainers, or `TEST_DATABASE_URL` / `KAFKA_BOOTSTRAP_SERVERS`); `npm run test:coverage` for unit tests and `E2E_BASE_URL=http://localhost:8080 npm run e2e` in `apps/web` for the browser tests against `make up`.

## The review screen
![Review screen, light theme](docs/screenshots/review-light.png)

Original note on the left, editable summary on the right. Selecting a field highlights the text that supports it; every field shows a confidence level and says plainly when something is not documented. Nothing is final until a clinician approves it. Dark theme and phone layouts: [`dark`](docs/screenshots/review-dark.png), [`mobile`](docs/screenshots/review-mobile.png). Design decisions: [`ADR-005`](docs/adr/ADR-005-frontend-design.md).

## How a note is processed
`POST /notes` -> note + outbox event saved in one transaction -> relay publishes `note.submitted` -> worker redacts PII (typed placeholders, map stored encrypted) -> LLM returns a structured summary with verbatim quotes -> pipeline validates, locates quotes, retries with the error fed back -> `PENDING_REVIEW`. Real values are restored only when the clinician opens the note. Details: [`docs/adr/ADR-004-pipeline-design.md`](docs/adr/ADR-004-pipeline-design.md).

## Results (offline run, `make eval`)
33 synthetic German and English notes, run through the real redaction and validation pipeline with the offline
keyword extractor, so these figures describe the pipeline and the gate, **not** how a language model performs.
Full report: [`docs/eval-report.md`](docs/eval-report.md). Method and dataset: [`eval/README.md`](eval/README.md).

| Metric | Baseline | With fixes |
|---|---|---|
| Field F1 (7 fields, micro) | 61.1% | 65.7% |
| Hallucination rate | 5.7% | 5.5% |
| Prompt-injection success | 50.0% | 50.0% |
| PII leak rate after redaction | 0.0% | 0.0% |
| Schema validation pass (first attempt) | 100.0% | 100.0% |

The fix measured here is the clinical-term guard in the redactor, which stops drug names from being
replaced by `[PERSON_n]`. The injection figure is a weakness of the keyword extractor, which copies
instructions found in a note; CI keeps it from getting worse and a real model is expected to resist better
(run `make -C eval run PROVIDER=openrouter`, which needs an API key). CI fails if the fixed variant regresses.

## Deploying
Images, a Helm chart, Terraform for AWS (EKS, RDS, ECR) and ArgoCD apps are in `infra/`; CI builds, scans and pushes images and updates the dev GitOps values. Dev syncs automatically, prod is promoted by hand. Step-by-step setup, a local Kubernetes path and teardown: [`docs/deploy.md`](docs/deploy.md). Design decisions: [`ADR-006`](docs/adr/ADR-006-delivery.md).

## Measured so far
- PII redaction on a small synthetic DE/EN corpus: see [`docs/pii-redaction-report.md`](docs/pii-redaction-report.md) (baseline vs. with a clinical-term guard; the corpus is small and was used while building the guard, so treat the figures as a regression gate).

## Repository layout
```
apps/web          React frontend
apps/api          FastAPI service (REST, auth, review workflow, audit log)
apps/worker       Kafka consumer (PII redaction + model pipeline)
packages/schemas  Shared JSON schema for the summary
infra/terraform   AWS: network, EKS, RDS, ECR, CI roles
infra/helm        Helm chart (api, worker, web, jobs, policies)
infra/argocd      ArgoCD project and dev/prod applications
docs/             ADRs, deploy guide, evaluation and PII reports
eval/             Evaluation dataset, runner and CI gate
scripts/          Helpers (tool runner, deploy configuration)
```

Architecture decisions: [`docs/adr/`](docs/adr/).
