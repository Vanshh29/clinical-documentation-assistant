# Threat model

Demo only. Not a medical device. Not for real patient data. Method: STRIDE over the data flows in [`architecture.md`](architecture.md).

**Assets:** note text (the most sensitive), the redaction map, summaries, the audit trail, credentials and signing secrets.
**Trust boundaries:** browser to web/API; API and worker to the database and broker; worker to the model service (outside our control); cluster to cloud APIs.
**Actors:** clinician, administrator, another clinician, an outsider, the text of a note itself (it can carry attacks), and the model service.

## The three risks the project is built around
| Risk | What stops it | How it is checked |
|---|---|---|
| **Prompt injection**: a note tries to give the model orders. | The system prompt marks the note as untrusted data. The model returns only a fixed JSON shape (unknown fields rejected). Every cited quote must exist verbatim in the note. A person reviews and approves every summary. | Four injection notes in the evaluation set; a forbidden-text check; UI test that the system prompt never appears. |
| **PII leakage**: personal data reaches the model, logs, queue or an admin. | Redaction runs before any model call. The placeholder map is encrypted (Fernet) in its own table. Kafka events and audit entries hold ids and counts only. Logs never carry note text. Admins cannot read notes. | Test that the model's input has no names, dates or numbers; ciphertext contains no plaintext; audit entries carry no note text; admin gets 403 on notes; redaction report. |
| **Broken access control**: reading or changing someone else's notes. | Every query is scoped to the owner; another person's note answers 404 (no probing by id); roles checked on each route; review actions take a row lock. | Tests for cross-user access, admin limits and refusal of a second approval; browser test with two clinicians. Row locking on review actions is by design but not load-tested. |

## STRIDE
| | Threat | Mitigation in place | Residual risk |
|---|---|---|---|
| **S**poofing | Forged or stolen token; guessing accounts | Signed tokens checked for issuer, audience and expiry; passwords hashed with scrypt; a dummy hash keeps unknown-account timing similar; the same error for bad email and bad password | The token issuer is a demo mock (ADR-002); no refresh or revocation; **no login rate limiting** |
| **T**ampering | Editing the audit trail or model output after the fact | Database triggers reject update, delete and truncate on `audit_log`; the model's output column is never updated, edits go to separate columns with a stored diff; invalid state changes are refused | A database superuser can still disable triggers; audit entries are not signed |
| **R**epudiation | "I never approved that" | Every submit, generation, edit, approval, rejection, regeneration and erasure is recorded with actor, request id, model, prompt and schema versions | Entries are only as trustworthy as the database; there is no external log shipping |
| **I**nformation disclosure | PII in storage, logs, errors, metrics, the browser | See PII row above. Strict CSP, no inline scripts, security headers; React escapes output; metrics on an internal port; failure reasons are codes, not text | `notes.body` and approved summaries are **plaintext in the database** (disk encryption on RDS only); the model service sees redacted text, which can still identify someone if recognizers miss something; the session token lives in `sessionStorage`, readable by any script that gets past the CSP |
| **D**enial of service | Oversize or hostile input; a slow or failing model | Note size limits in browser, API and proxy; timeouts; bounded retries with backoff; circuit breaker; stuck-note reaper; resource limits and autoscaling; the heartbeat restarts a wedged worker | No per-user quotas or API rate limits; the queue can grow without bound under sustained load |
| **E**levation of privilege | Admin or clinician exceeding their role; container breakout | Roles enforced per route; admins see aggregates only; pods run as non-root with a read-only filesystem, no capabilities and a default seccomp profile; default-deny network policies; narrowly scoped cloud roles; CI uses short-lived OIDC credentials | Network policy needs a CNI that enforces it; cluster add-ons are outside this repository |

## Supply chain and operations
The Kubernetes API endpoint is private by default; public access is opt-in, needs an explicit address list, and `0.0.0.0/0` is rejected by the Terraform variable validation. Base images are kept current: the first CI scan failed on fixable HIGH and CRITICAL findings in months-old base images, and the build now fails on any such finding.
Pinned base images and immutable image tags; dependency audits, image and configuration scans, and secret scanning in CI; Dependabot. Terraform state is encrypted and locked. Residual: GitHub Actions are pinned by version tag, not commit hash; the model service is a third party whose retention policy must be reviewed before any real use.

## Not covered
Real patient data, regulatory compliance, a security review by a third party, penetration testing, and data-protection impact assessment. Do not put real data into this system.

## Findings fixed while building
Found by tests or by exercising the running system, then fixed and covered by a test: concurrent migrations could collide; a failed session-restore request signed users out and deleted their token; the worker's stuck-note reaper died on a database error and stopped the heartbeat; the redactor treated drug names as people and stripped clinical content; a model citing a quote for an undocumented field crashed span resolution instead of triggering a retry.
