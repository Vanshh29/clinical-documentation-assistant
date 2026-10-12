# ADR-003: API design decisions

- Status: Accepted
- Date: 2026-10-12

## Decisions
1. **Transactional outbox.** Submitting a note writes the `Note`, an `outbox_events` row and an audit entry in one transaction. A relay (Phase 3) publishes to Kafka. This avoids the dual-write problem: a note is never saved without its event, or the reverse.
2. **Events carry ids, not text.** `note.submitted` holds `note_id` and `generation`. The worker loads the note itself, so Kafka never stores clinical text.
3. **Append-only audit log enforced in the database.** Triggers reject `UPDATE`, `DELETE` and `TRUNCATE`, so the guarantee does not depend on application code. Entries hold ids, counters and versions, never note text or free-text reasons.
4. **Least privilege for admins.** Admins read the audit log and aggregate metrics but get 403 on note content. Another clinician's note returns 404, so ids cannot be probed.
5. **Model output is immutable.** `summaries.content` is never updated. Edits go to `edited_content`, approval writes `approved_content` and a field-level `diff`, which feeds the edit-rate metric.
6. **Row locks on review actions.** Approve, reject, edit and regenerate use `SELECT ... FOR UPDATE` on the note so concurrent actions cannot both succeed.
7. **Regeneration keeps history.** Each generation is its own `summaries` row (`UNIQUE(note_id, generation)`).
8. **Right to erasure.** `DELETE /me/data` hard-deletes the caller's notes; summaries, mappings and call metrics cascade. The audit log keeps only an `data.erased` entry with a count.

## Trade-offs
- Application services use SQLAlchemy sessions directly instead of repository interfaces. The domain package imports no framework code; a repository layer would add indirection without a second implementation to justify it.
- `pyjwt` is added beyond the stack list in ADR-001: hand-rolling JWT verification would be worse.
