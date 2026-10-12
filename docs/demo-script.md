# Two-minute demo

Setup (before the demo): `make up`, then open http://localhost:8080 in a clean window. Offline provider, so no key or network is needed.

| Time | Do | Say |
|---|---|---|
| 0:00 | Show the banner at the top | "Demo only, synthetic data. A clinician pastes a note and gets a structured summary to review. A person approves everything." |
| 0:10 | Sign in: **Fill clinician login**, **Sign in** | "Roles are enforced on the server: clinicians see only their own notes." |
| 0:20 | **New note**, **German example**, **Submit for summary** | "Names, dates and numbers are replaced with placeholders before the model sees anything." |
| 0:30 | The progress screen turns into the review screen (about a second) | "That went through Postgres, Kafka and the worker. It is asynchronous, so a slow model never blocks the page." |
| 0:40 | Click **Source** on *Medications mentioned* | "Each field highlights the exact text it came from. The model has to quote the note word for word, and the quotes are checked." |
| 0:55 | Point at the confidence badges and *Not documented* | "If the note doesn't say it, the field stays empty. It never guesses." |
| 1:05 | Edit the **Plan**, **Save draft** | "Edits are kept separately; the model's original output is never overwritten." |
| 1:20 | **Approve**. Read the dialog ("1 field changed"), confirm | "Approval is explicit and final. The diff against the model's output feeds the edit-rate metric." |
| 1:30 | Show the green *Approved* banner | "Only approved summaries count as final." |
| 1:35 | **Sign out**, sign in as admin (**Fill admin login**) | "Admins get aggregates and the audit trail, never note text." |
| 1:45 | **Metrics** tab, then **Audit log** | "Approval rate, edit rate, latency and cost per note. The audit log records who did what, with model and prompt versions, and holds only ids." |
| 1:55 | Close on the terminal: `make eval` | "Quality is measured in CI: 33 synthetic German and English notes, and the build fails if it regresses." |

Optional proof of privacy (10 seconds), in a terminal:
```bash
docker compose exec postgres psql -U cda -d cda -c \
  "select content->'chief_complaint'->>'value' as stored_in_db from summaries order by created_at desc limit 1"
```
It shows `[PERSON_1]` / `[DOB_1]` placeholders in the database, while the screen shows the real values.

If asked what is next: a real identity provider, deployment to a real cluster, and measuring a real model with `make -C eval run PROVIDER=openrouter`.
