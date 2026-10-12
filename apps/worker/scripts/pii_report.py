"""Measure redaction quality on the synthetic corpus and write docs/pii-redaction-report.md.

Run: PYTHONPATH=src:../api/src:. .venv/bin/python scripts/pii_report.py [--print-only]
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from tests.pii_corpus import CASES

from cda_worker.adapters.redactor import PresidioRedactor


@dataclass
class Scores:
    pii_total: int
    pii_caught: int
    spans_found: int
    spans_correct: int
    keep_total: int
    keep_intact: int
    misses: list[str]
    false_hits: list[str]
    damaged: list[str]

    @property
    def recall(self) -> float:
        return self.pii_caught / self.pii_total

    @property
    def precision(self) -> float:
        return self.spans_correct / self.spans_found

    @property
    def retention(self) -> float:
        return self.keep_intact / self.keep_total


def score(redactor: PresidioRedactor) -> Scores:
    s = Scores(0, 0, 0, 0, 0, 0, [], [], [])
    for _lang, text, pii, keep in CASES:
        res = redactor.redact(text, _lang)
        for p in pii:
            s.pii_total += 1
            if p not in res.text:
                s.pii_caught += 1
            else:
                s.misses.append(p)
        for r in res.mapping.replacements:
            s.spans_found += 1
            if any(r.original in p or p in r.original for p in pii):
                s.spans_correct += 1
            else:
                s.false_hits.append(r.original)
        for k in keep:
            s.keep_total += 1
            if k in res.text:
                s.keep_intact += 1
            else:
                s.damaged.append(k)
    return s


def row(name: str, s: Scores) -> str:
    return (
        f"| {name} | {s.recall:.1%} ({s.pii_caught}/{s.pii_total}) | "
        f"{s.precision:.1%} ({s.spans_correct}/{s.spans_found}) | "
        f"{s.retention:.1%} ({s.keep_intact}/{s.keep_total}) |"
    )


def main() -> None:
    base = score(PresidioRedactor(guard_clinical_terms=False))
    fixed = score(PresidioRedactor(guard_clinical_terms=True))
    lines = [
        "# PII redaction report",
        "",
        "Synthetic German + English corpus (`apps/worker/tests/pii_corpus.py`, "
        f"{len(CASES)} sentences, {fixed.pii_total} PII strings, {fixed.keep_total} clinical "
        "phrases that must survive).",
        "",
        "Reproduce: `cd apps/worker && PYTHONPATH=src:../api/src:. .venv/bin/python scripts/pii_report.py`",
        "",
        "| Variant | Recall (PII removed) | Precision (redactions that were PII) | Clinical text retained |",
        "|---|---|---|---|",
        row("Baseline: Presidio + spaCy small models + regex", base),
        row("With clinical-term guard (drug names kept)", fixed),
        "",
        "## Remaining errors (with guard)",
        f"- PII not removed: {fixed.misses or 'none'}",
        f"- Redactions that were not PII: {fixed.false_hits or 'none'}",
        f"- Clinical phrases damaged: {fixed.damaged or 'none'}",
        "",
        "## Baseline errors (without guard)",
        f"- PII not removed: {base.misses or 'none'}",
        f"- Redactions that were not PII: {base.false_hits or 'none'}",
        f"- Clinical phrases damaged: {base.damaged or 'none'}",
        "",
        "Limits: small corpus, synthetic text, spaCy *small* models. The clinical-term guard was "
        "developed while looking at this same corpus, so its numbers are optimistic until re-measured "
        "on a held-out set. They are a regression gate, not a guarantee. Do not use with real "
        "patient data.",
    ]
    text = "\n".join(lines) + "\n"
    print(text)
    if "--print-only" not in sys.argv:
        out = Path(__file__).resolve().parents[3] / "docs" / "pii-redaction-report.md"
        out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
