import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from cda_eval.cases import CASES, FIELDS, Case
from cda_eval.metrics import RunMetrics
from cda_eval.runner import METRIC_GETTERS, VARIANTS

LABELS = {
    "chief_complaint": "Chief complaint",
    "history_of_present_illness": "History of present illness",
    "medications": "Medications",
    "allergies": "Allergies",
    "assessment": "Assessment",
    "plan": "Plan",
    "follow_up_items": "Follow-up items",
}


def dataset_fingerprint(cases: list[Case] = CASES) -> str:
    payload = json.dumps(
        [[c.id, c.language, c.category, c.text, c.gold, c.pii, c.forbidden] for c in cases],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def pct(v: float | None, digits: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{digits}f}%"


def delta(f: float, b: float, higher_better: bool) -> str:
    d = (f - b) * 100
    if abs(d) < 0.05:
        return "no change"
    better = d > 0 if higher_better else d < 0
    return f"{'+' if d > 0 else ''}{d:.1f} pts ({'better' if better else 'worse'})"


def summary_dict(m: RunMetrics) -> dict[str, Any]:
    out: dict[str, Any] = {"variant": m.variant, "n_cases": m.n_cases}
    out.update({name: round(getter(m), 4) for name, getter in METRIC_GETTERS.items()})
    out.update(
        {
            "truncated_cases": m.truncated_cases,
            "latency_ms_p50": round(m.latency_ms_p50, 2),
            "latency_ms_p95": round(m.latency_ms_p95, 2),
            "wall_ms_p50": round(m.wall_ms_p50, 2),
            "wall_ms_p95": round(m.wall_ms_p95, 2),
            "input_tokens_mean": round(m.input_tokens_mean, 1),
            "output_tokens_mean": round(m.output_tokens_mean, 1),
            "cost_usd_mean": round(m.cost_usd_mean, 6),
            "cost_usd_total": round(m.cost_usd_total, 6),
            "per_field_f1": {n: round(c.f1, 4) for n, c in m.fields.items()},
            "per_field_accuracy": {n: round(c.accuracy, 4) for n, c in m.fields.items()},
        }
    )
    return out


def render(
    results: dict[str, RunMetrics], *, provider: str, model: str, command: str, limit: int | None
) -> str:
    fixed = results.get("fixed") or next(iter(results.values()))
    base = results.get("baseline")
    langs = Counter(c.language for c in CASES)
    cats = Counter(c.category for c in CASES)
    when = datetime.now(UTC).date().isoformat()
    L: list[str] = ["# Evaluation report", ""]
    L += [
        f"- **Generated:** {when}",
        f"- **Provider / model:** `{provider}` / `{model}`",
        f"- **Dataset:** {fixed.n_cases} synthetic notes"
        + (f" (first {limit} of {len(CASES)})" if limit else "")
        + f" - German {langs['de']}, English {langs['en']} - "
        + ", ".join(f"{k} {v}" for k, v in sorted(cats.items()))
        + f" - fingerprint `{dataset_fingerprint()}`",
        f"- **Reproduce:** `{command}`",
        "",
    ]
    if provider == "fake":
        L += [
            "> **Read this first.** The `fake` provider is a keyword extractor used for offline runs and CI. "
            "These numbers measure the *pipeline* (redaction, validation, scoring) and give CI a stable "
            "regression gate. They say nothing about how a real language model performs. Run "
            "`make eval PROVIDER=openrouter` with a key to measure one.",
            "",
        ]
    L += ["## Variants compared", ""]
    for name in results:
        v = VARIANTS[name]
        L.append(f"- **{name}**: {v.description}")
    L += ["", "## Headline metrics", ""]
    header = "| Metric | " + " | ".join(results) + (" | Change |" if base else " |")
    L += [header, "|---|" + "---|" * (len(results) + (1 if base else 0))]

    def row(label: str, key: str, fmt: Any, higher: bool) -> None:
        cells = [fmt(METRIC_GETTERS[key](m)) for m in results.values()]
        extra = ""
        if base and fixed is not base:
            extra = (
                " " + delta(METRIC_GETTERS[key](fixed), METRIC_GETTERS[key](base), higher) + " |"
            )
        L.append(f"| {label} | " + " | ".join(cells) + (f" |{extra}" if base else " |"))

    row("Field F1 (micro, all fields)", "overall_f1", pct, True)
    row("Field precision", "overall_precision", pct, True)
    row("Field recall", "overall_recall", pct, True)
    row("Notes fully correct (all 7 fields)", "exact_case_rate", pct, True)
    row("Hallucination rate (values citing text not in the note)", "hallucination_rate", pct, False)
    row("Overreach rate (filled a field the note leaves empty)", "overreach_rate", pct, False)
    row("Prompt-injection success rate", "injection_success_rate", pct, False)
    row("PII leak rate after redaction", "pii_leak_rate", pct, False)
    row("Schema validation pass, first attempt", "first_pass_rate", pct, True)
    row("Schema validation pass, after retries", "final_pass_rate", pct, True)

    L += [
        "",
        "## Cost and speed",
        "",
        "| Measure | " + " | ".join(results) + " |",
        "|---|" + "---|" * len(results),
    ]
    L.append(
        "| Model latency p50 / p95 | "
        + " | ".join(
            f"{m.latency_ms_p50:.0f} / {m.latency_ms_p95:.0f} ms" for m in results.values()
        )
        + " |"
    )
    L.append(
        "| Per-note wall time p50 / p95 (redaction + model) | "
        + " | ".join(f"{m.wall_ms_p50:.0f} / {m.wall_ms_p95:.0f} ms" for m in results.values())
        + " |"
    )
    L.append(
        "| Tokens per note (in / out) | "
        + " | ".join(
            f"{m.input_tokens_mean:.0f} / {m.output_tokens_mean:.0f}" for m in results.values()
        )
        + " |"
    )
    L.append(
        "| Estimated cost per note | "
        + " | ".join(f"${m.cost_usd_mean:.4f}" for m in results.values())
        + " |"
    )
    L.append(
        "| Notes truncated to the input limit | "
        + " | ".join(str(m.truncated_cases) for m in results.values())
        + " |"
    )

    L += [
        "",
        f"## Accuracy by field ({fixed.variant})",
        "",
        "| Field | Exact | Precision | Recall | F1 |",
        "|---|---|---|---|---|",
    ]
    for name in FIELDS:
        c = fixed.fields[name]
        L.append(
            f"| {LABELS[name]} | {pct(c.accuracy)} | {pct(c.precision)} | {pct(c.recall)} | {pct(c.f1)} |"
        )

    L += [
        "",
        f"## F1 by note type ({fixed.variant})",
        "",
        "| Group | F1 | Notes |",
        "|---|---|---|",
    ]
    n_cat = Counter(c.category for c in CASES)
    for k, c in sorted(fixed.by_category.items()):
        L.append(f"| {k} | {pct(c.f1)} | {n_cat[k]} |")
    n_lang = Counter(c.language for c in CASES)
    for k, c in sorted(fixed.by_language.items()):
        L.append(
            f"| language: {'German' if k == 'de' else 'English'} | {pct(c.f1)} | {n_lang[k]} |"
        )

    L += ["", "## Redaction", ""]
    if fixed.pii_leaked_items:
        L.append(
            f"PII strings still present after redaction ({fixed.variant}): "
            + "; ".join(f"`{x}`" for x in fixed.pii_leaked_items)
        )
    else:
        L.append("No gold PII string survived redaction.")
    L += [
        "",
        "There is no dedicated street-address recognizer. The two addresses in the dataset were "
        "removed by the NER place model; other address formats are untested, so treat addresses as "
        "a known gap.",
        "",
    ]

    L += [f"## Notes with at least one wrong field ({fixed.variant})", ""]
    L += [f"- {x}" for x in fixed.misses] or ["- none"]
    L += [
        "",
        "## Method and limits",
        "",
        "- Gold annotations are key phrases written from the note text alone (`eval/cda_eval/cases.py`). A "
        "text field is correct if every key is present; a list field is correct if every key is matched "
        "and no extra item is returned. Precision/recall/F1 are micro-averaged over fields and items.",
        "- *Hallucination* flags a filled value containing a number, or at least a third of its words, "
        "that the note text sent to the model does not contain. A German note summarised in English "
        "words counts as unsupported.",
        "- *Prompt-injection success* means a forbidden string (text only the system prompt contains, or a "
        "diagnosis an injected instruction asks for) appears in any output value.",
        "- 33 notes is small: one note moves a rate by 3 points. Use the numbers to compare variants and "
        "to catch regressions, not as a claim about clinical accuracy.",
        "- Long notes are cut at the input limit, so facts after the cut are lost by design "
        "(see ADR-004).",
        "",
    ]
    return "\n".join(L)
