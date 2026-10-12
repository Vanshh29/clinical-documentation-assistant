# Architecture

Demo only. Not a medical device. Not for real patient data.

## System overview
A clinician submits a note. The API stores it and queues work; a worker removes personal data, asks a model for a structured summary, checks the answer, and stores it for the clinician to review. Nothing is final until a person approves it.

```mermaid
flowchart LR
  subgraph Browser
    UI[React app]
  end
  subgraph Cluster["Kubernetes (or Docker Compose)"]
    WEB[web<br/>nginx, CSP, /api proxy]
    API[api<br/>FastAPI]
    RELAY[outbox relay]
    WORKER[worker<br/>redact, model, validate]
    CRON[retention CronJob]
    KAFKA[(Kafka<br/>note.submitted<br/>summary.ready)]
  end
  PG[(PostgreSQL 16)]
  LLM[Model API<br/>OpenRouter or offline provider]
  SM[Secrets Manager]
  PROM[Prometheus]

  UI -->|HTTPS| WEB -->|/api| API
  API -->|note + outbox event, one transaction| PG
  RELAY -->|poll unpublished rows| PG
  RELAY -->|publish| KAFKA
  KAFKA -->|consume| WORKER
  WORKER -->|redacted text only| LLM
  WORKER -->|summary, encrypted PII map, metrics| PG
  CRON -->|delete expired notes| PG
  SM -.->|External Secrets| API
  SM -.-> WORKER
  PROM -.->|scrape :9100, internal| API
  PROM -.-> WORKER
```
The relay runs inside the worker process. Metrics are on a separate internal port, so the public path never reaches them.

## What happens to one note
```mermaid
sequenceDiagram
  actor C as Clinician
  participant W as Web
  participant A as API
  participant D as Postgres
  participant K as Kafka
  participant X as Worker
  participant M as Model

  C->>W: paste note, submit
  W->>A: POST /notes
  A->>D: note (SUBMITTED) + outbox event + audit entry
  A-->>W: 201, note id
  Note over W: page polls the note every 1.5 s
  X->>D: poll outbox, mark published
  X->>K: note.submitted (ids only, no text)
  K->>X: deliver
  X->>D: claim note (SUBMITTED to PROCESSING)
  X->>X: redact: [PERSON_1], [DOB_1] ...
  X->>D: store encrypted placeholder map
  X->>M: redacted text, prompt v1
  M-->>X: JSON with verbatim quotes
  X->>X: validate schema, locate quotes, retry with errors if needed
  X->>D: summary (PENDING_REVIEW) + metrics + summary.ready event
  W->>A: GET /notes/id
  A->>D: summary + encrypted map
  A-->>W: real values restored, offsets mapped to the original text
  C->>W: review, edit, approve
  W->>A: POST /notes/id/approve
  A->>D: approved content, diff against model output, audit entry
```

## Note states
```mermaid
stateDiagram-v2
  [*] --> SUBMITTED
  SUBMITTED --> PROCESSING: worker claims it
  PROCESSING --> PENDING_REVIEW: valid summary
  PROCESSING --> FAILED_VALIDATION: invalid after retries, model down, timeout
  PENDING_REVIEW --> APPROVED: clinician approves
  PENDING_REVIEW --> REJECTED: clinician rejects (reason required)
  PENDING_REVIEW --> SUBMITTED: regenerate
  FAILED_VALIDATION --> SUBMITTED: retry
  APPROVED --> [*]
  REJECTED --> [*]
```
Invalid moves are refused by one function (`domain/state_machine.py`) and the API answers 409.

## Data model
```mermaid
erDiagram
  users ||--o{ notes : owns
  notes ||--o{ summaries : "one per generation"
  notes ||--o| pii_mappings : "encrypted map"
  notes ||--o{ llm_calls : metrics
  users { uuid id PK
          text email UK
          text role "clinician or admin" }
  notes { uuid id PK
          uuid owner_id FK
          text body
          text status
          int generation }
  summaries { uuid id PK
              uuid note_id FK
              int generation
              jsonb content "model output, never edited"
              jsonb edited_content
              jsonb approved_content
              jsonb diff }
  pii_mappings { uuid note_id PK
                 bytea ciphertext "Fernet" }
  llm_calls { uuid id PK
              uuid note_id FK
              text model
              int input_tokens
              int output_tokens
              numeric cost_usd }
  audit_log { bigint id PK
              text action
              uuid entity_id
              jsonb details "ids and counts only" }
  outbox_events { uuid id PK
                  text topic
                  jsonb payload "ids only"
                  timestamptz published_at }
```
`audit_log` has no foreign keys and is append-only (database triggers reject update, delete and truncate), so erasing a user's notes never touches the audit trail. `outbox_events` is the transactional outbox.

## Delivery
```mermaid
flowchart LR
  DEV[push to main] --> CI[CI: tests, scans, eval gate]
  CI --> BUILD[build + scan images]
  BUILD --> ECR[(ECR, immutable tags)]
  BUILD --> GIT[commit tag to values-dev.yaml]
  GIT --> ARGO[ArgoCD]
  ARGO -->|auto sync, self-heal| DEVNS[cda-dev]
  PROMOTE[promote-prod workflow] --> PR[pull request: values-prod.yaml]
  PR --> ARGO
  ARGO -->|manual sync| PRODNS[cda-prod]
  TF[Terraform] --> AWS[VPC, EKS, RDS, ECR, IAM]
```
Details: [`deploy.md`](deploy.md) and [`adr/ADR-006-delivery.md`](adr/ADR-006-delivery.md).

## Layers
`apps/api/src/cda_api` is split ports-and-adapters style. `domain/` holds the state machine, summary schema, diff and redaction map and imports no web, broker or model library. `application/` holds the use cases. `adapters/` holds Postgres, crypto and token code. `api/` holds the HTTP layer. The worker follows the same shape: `domain/` (ports, prompts, validation loop) and `adapters/` (Presidio, providers, Kafka).

Related decisions: [ADR-001](adr/ADR-001-tech-stack.md) stack, [ADR-002](adr/ADR-002-auth-and-cloud-target.md) auth and cloud, [ADR-003](adr/ADR-003-api-design-decisions.md) API, [ADR-004](adr/ADR-004-pipeline-design.md) pipeline, [ADR-005](adr/ADR-005-frontend-design.md) frontend, [ADR-006](adr/ADR-006-delivery.md) delivery.
