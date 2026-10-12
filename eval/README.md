# Evaluation harness

Measures how well the processing pipeline turns notes into correct, supported, safe summaries, and stops
regressions from merging.

```bash
make eval                      # from the repo root: baseline vs fixed, writes docs/eval-report.md, gates CI
make -C eval test              # tests for the dataset, scoring and gate
make -C eval run PROVIDER=openrouter   # real model; needs OPENROUTER_API_KEY and LLM_MODEL in the environment
                                       # and credit on the account; writes docs/eval-report-openrouter.md
```

It calls the same functions the worker runs (redaction, input limit, generation with validation and
retries), so no database or broker is needed. Needs the worker virtualenv (`make -C apps/worker install`).

## Dataset (`cda_eval/cases.py`)
33 invented notes: 18 English, 15 German. Types: clean (12), messy abbreviations, fragments and
unpunctuated dictation (7), missing sections (4), contradictory content (3), prompt injection (4), identifier-heavy
(2), and one very long note that exceeds the input limit. Gold annotations are key phrases written from the
note text alone; a test checks every key really occurs in its note.

## Metrics
| Metric | Meaning |
|---|---|
| Field F1 / precision / recall | micro-averaged over the 7 summary fields and list items |
| Notes fully correct | all 7 fields right (strict) |
| Hallucination rate | filled values citing numbers, or many words, absent from the note |
| Overreach rate | a field the note leaves empty was filled in |
| Injection success rate | forbidden text (system prompt, or an injected diagnosis) reached an output value |
| PII leak rate | gold identifiers still present in the redacted text |
| Schema pass rate | valid on the first attempt / after retries |
| Latency, tokens, cost | per note, from the provider's own reporting |

## Variants
- **baseline**: plain Presidio redaction, no validation retries.
- **fixed**: clinical-term guard in the redactor (keeps drug names that the NER model mistakes for people)
  and up to two validation retries.

## The CI gate (`thresholds.json`)
`make eval` fails if the fixed variant falls below recorded floors, rises above recorded ceilings, or is worse
than the baseline on F1, PII leakage or hallucination. Thresholds are the measured values plus a 3-point
allowance. To re-record after an intentional change: `make -C eval thresholds`, then review the diff.
The gate only runs for the offline `fake` provider, which is deterministic; real-model runs are reported,
not gated.

## Adding a case
Append a `Case` to `CASES`. Keep it fictional. Write gold from the note, not from model output. Run
`make -C eval test`; if the dataset changes, re-run `make eval` and commit the new report.
