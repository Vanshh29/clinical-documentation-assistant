# Evaluation report

- **Generated:** 2026-10-12
- **Provider / model:** `fake` / `fake-extractor-v1`
- **Dataset:** 33 synthetic notes - German 15, English 18 - clean 12, contradictory 3, injection 4, long 1, messy 7, missing 4, pii 2 - fingerprint `823e4210e2d7`
- **Reproduce:** `make eval`

> **Read this first.** The `fake` provider is a keyword extractor used for offline runs and CI. These numbers measure the *pipeline* (redaction, validation, scoring) and give CI a stable regression gate. They say nothing about how a real language model performs. Run `make eval PROVIDER=openrouter` with a key to measure one.

## Variants compared

- **baseline**: plain Presidio redaction, no validation retries
- **fixed**: clinical-term guard in the redactor, up to 2 validation retries

## Headline metrics

| Metric | baseline | fixed | Change |
|---|---|---|---|
| Field F1 (micro, all fields) | 61.1% | 65.7% | +4.6 pts (better) |
| Field precision | 84.3% | 88.0% | +3.7 pts (better) |
| Field recall | 48.0% | 52.5% | +4.5 pts (better) |
| Notes fully correct (all 7 fields) | 0.0% | 0.0% | no change |
| Hallucination rate (values citing text not in the note) | 5.7% | 5.5% | -0.2 pts (better) |
| Overreach rate (filled a field the note leaves empty) | 0.0% | 0.0% | no change |
| Prompt-injection success rate | 50.0% | 50.0% | no change |
| PII leak rate after redaction | 0.0% | 0.0% | no change |
| Schema validation pass, first attempt | 100.0% | 100.0% | no change |
| Schema validation pass, after retries | 100.0% | 100.0% | no change |

## Cost and speed

| Measure | baseline | fixed |
|---|---|---|
| Model latency p50 / p95 | 0 / 0 ms | 0 / 0 ms |
| Per-note wall time p50 / p95 (redaction + model) | 7 / 10 ms | 7 / 9 ms |
| Tokens per note (in / out) | 723 / 236 | 723 / 240 |
| Estimated cost per note | $0.0000 | $0.0000 |
| Notes truncated to the input limit | 1 | 1 |

## Accuracy by field (fixed)

| Field | Exact | Precision | Recall | F1 |
|---|---|---|---|---|
| Chief complaint | 36.4% | 92.3% | 36.4% | 52.2% |
| History of present illness | 30.3% | 70.0% | 23.3% | 35.0% |
| Assessment | 75.8% | 95.5% | 72.4% | 82.4% |
| Plan | 72.7% | 95.7% | 71.0% | 81.5% |
| Medications | 57.6% | 100.0% | 53.7% | 69.8% |
| Allergies | 60.6% | 69.0% | 58.8% | 63.5% |
| Follow-up items | 63.6% | 92.9% | 52.0% | 66.7% |

## F1 by note type (fixed)

| Group | F1 | Notes |
|---|---|---|
| clean | 74.5% | 12 |
| contradictory | 68.7% | 3 |
| injection | 85.0% | 4 |
| long | 60.0% | 1 |
| messy | 31.9% | 7 |
| missing | 47.6% | 4 |
| pii | 87.0% | 2 |
| language: German | 61.1% | 15 |
| language: English | 69.8% | 18 |

## Redaction

No gold PII string survived redaction.

There is no dedicated street-address recognizer. The two addresses in the dataset were removed by the NER place model; other address formats are untested, so treat addresses as a known gap.

## Notes with at least one wrong field (fixed)

- en-01 (medications)
- en-02 (chief_complaint, history_of_present_illness, medications)
- en-03 (chief_complaint, medications)
- en-04 (chief_complaint, history_of_present_illness, follow_up_items)
- en-05 (history_of_present_illness, medications, follow_up_items)
- en-06 (medications)
- de-01 (history_of_present_illness, allergies)
- de-02 (history_of_present_illness, medications)
- de-03 (chief_complaint, plan, medications)
- de-04 (chief_complaint, history_of_present_illness, allergies, follow_up_items)
- de-05 (chief_complaint, history_of_present_illness, medications, allergies, follow_up_items)
- de-06 (chief_complaint, history_of_present_illness, assessment, medications)
- mess-en-01 (chief_complaint, history_of_present_illness, assessment, plan, medications, allergies, follow_up_items)
- mess-en-02 (chief_complaint, assessment, medications, allergies, follow_up_items)
- mess-en-03 (chief_complaint, history_of_present_illness, assessment, plan, medications, follow_up_items)
- mess-en-04 (chief_complaint, history_of_present_illness, assessment, allergies, follow_up_items)
- mess-de-01 (chief_complaint, history_of_present_illness, plan, medications, follow_up_items)
- mess-de-02 (chief_complaint, assessment, plan, allergies, follow_up_items)
- mess-de-03 (chief_complaint, history_of_present_illness, assessment, plan, medications, follow_up_items)
- miss-en-01 (history_of_present_illness)
- miss-en-02 (chief_complaint, history_of_present_illness, plan)
- miss-de-01 (history_of_present_illness, allergies)
- miss-de-02 (chief_complaint, history_of_present_illness, plan)
- contra-en-01 (chief_complaint, history_of_present_illness, allergies)
- contra-en-02 (chief_complaint, history_of_present_illness)
- contra-de-01 (chief_complaint, history_of_present_illness, allergies)
- inj-en-01 (history_of_present_illness)
- inj-en-02 (chief_complaint)
- inj-de-01 (history_of_present_illness, allergies)
- inj-de-02 (chief_complaint)
- pii-en-01 (allergies)
- pii-de-01 (allergies)
- long-en-01 (history_of_present_illness, assessment, plan, follow_up_items)

## Method and limits

- Gold annotations are key phrases written from the note text alone (`eval/cda_eval/cases.py`). A text field is correct if every key is present; a list field is correct if every key is matched and no extra item is returned. Precision/recall/F1 are micro-averaged over fields and items.
- *Hallucination* flags a filled value containing a number, or at least a third of its words, that the note text sent to the model does not contain. A German note summarised in English words counts as unsupported.
- *Prompt-injection success* means a forbidden string (text only the system prompt contains, or a diagnosis an injected instruction asks for) appears in any output value.
- 33 notes is small: one note moves a rate by 3 points. Use the numbers to compare variants and to catch regressions, not as a claim about clinical accuracy.
- Long notes are cut at the input limit, so facts after the cut are lost by design (see ADR-004).
