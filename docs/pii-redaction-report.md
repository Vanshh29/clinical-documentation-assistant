# PII redaction report

Synthetic German + English corpus (`apps/worker/tests/pii_corpus.py`, 24 sentences, 36 PII strings, 33 clinical phrases that must survive).

Reproduce: `cd apps/worker && PYTHONPATH=src:../api/src:. .venv/bin/python scripts/pii_report.py`

| Variant | Recall (PII removed) | Precision (redactions that were PII) | Clinical text retained |
|---|---|---|---|
| Baseline: Presidio + spaCy small models + regex | 100.0% (36/36) | 85.7% (36/42) | 87.9% (29/33) |
| With clinical-term guard (drug names kept) | 100.0% (36/36) | 100.0% (36/36) | 100.0% (33/33) |

## Remaining errors (with guard)
- PII not removed: none
- Redactions that were not PII: none
- Clinical phrases damaged: none

## Baseline errors (without guard)
- PII not removed: none
- Redactions that were not PII: ['Metformin', 'Kontakt', 'Blutdruck', 'Tel.', 'Rückenschmerzen', 'Ibuprofen']
- Clinical phrases damaged: ['Metformin 500 mg', 'Blutdruck 150/95 mmHg', 'Rückenschmerzen', 'Ibuprofen 400 mg']

Limits: small corpus, synthetic text, spaCy *small* models. The clinical-term guard was developed while looking at this same corpus, so its numbers are optimistic until re-measured on a held-out set. They are a regression gate, not a guarantee. Do not use with real patient data.
