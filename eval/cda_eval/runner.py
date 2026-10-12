"""Runs the real pipeline pieces (redaction -> truncation -> generation/validation) on the dataset.

No database or broker is needed: the same functions the worker calls are used directly.
"""

import asyncio
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from cda_worker.adapters.fake_provider import FakeProvider
from cda_worker.adapters.openrouter_provider import OpenRouterProvider
from cda_worker.adapters.redactor import PresidioRedactor
from cda_worker.domain.generation import generate_validated
from cda_worker.domain.limits import truncate_to_budget
from cda_worker.domain.ports import LLMProvider
from cda_worker.domain.prompts import PromptBuilder

from cda_eval.cases import Case
from cda_eval.metrics import RunMetrics, aggregate, score_case


@dataclass(frozen=True)
class Variant:
    name: str
    guard_clinical_terms: bool
    validation_retries: int
    description: str


VARIANTS: dict[str, Variant] = {
    "baseline": Variant("baseline", False, 0, "plain Presidio redaction, no validation retries"),
    "fixed": Variant(
        "fixed", True, 2, "clinical-term guard in the redactor, up to 2 validation retries"
    ),
}


def build_provider(kind: str) -> tuple[LLMProvider, str]:
    if kind == "fake":
        return FakeProvider(), FakeProvider.model
    if kind == "openrouter":
        key, model = os.environ.get("OPENROUTER_API_KEY", ""), os.environ.get("LLM_MODEL", "")
        if not key or not model:
            raise SystemExit(
                "OPENROUTER_API_KEY and LLM_MODEL must be set for --provider openrouter"
            )
        return (
            OpenRouterProvider(
                key,
                model,
                # Reasoning models can take well over a minute per note.
                timeout_seconds=float(os.environ.get("LLM_TIMEOUT_SECONDS", "300")),
                price_in_per_mtok=Decimal(os.environ.get("LLM_PRICE_IN_PER_MTOK", "0")),
                price_out_per_mtok=Decimal(os.environ.get("LLM_PRICE_OUT_PER_MTOK", "0")),
            ),
            model,
        )
    raise SystemExit(f"unknown provider {kind!r}")


async def run_variant(
    variant: Variant,
    cases: list[Case],
    provider: LLMProvider,
    model_name: str,
    *,
    max_input_tokens: int = 8000,
    concurrency: int = 1,
    prompt_version: str = "v2",
) -> tuple[RunMetrics, list[dict[str, Any]]]:
    redactor = PresidioRedactor(guard_clinical_terms=variant.guard_clinical_terms)
    builder = PromptBuilder(prompt_version)
    gate = asyncio.Semaphore(concurrency)

    async def one(case: Case) -> dict[str, Any]:
        async with gate:
            started = time.perf_counter()
            redaction = await asyncio.to_thread(redactor.redact, case.text, case.language)
            model_input, truncated = truncate_to_budget(redaction.text, max_input_tokens)
            outcome = await generate_validated(
                provider,
                builder,
                model_input,
                max_validation_retries=variant.validation_retries,
                model_name=model_name,
            )
            wall_ms = (time.perf_counter() - started) * 1000
        summary = outcome.summary.model_dump(mode="json") if outcome.summary else None
        return {
            "case": case,
            "summary": summary,
            "failure_reason": outcome.failure_reason,
            "retries": outcome.retries,
            "truncated": truncated,
            "latency_ms": outcome.latency_ms,
            "wall_ms": wall_ms,
            "input_tokens": outcome.input_tokens,
            "output_tokens": outcome.output_tokens,
            "cost_usd": outcome.cost_usd,
            "score": score_case(case, summary, model_input, redaction.text),
        }

    rows = list(await asyncio.gather(*(one(c) for c in cases)))
    return aggregate(variant.name, rows), rows


# ---- regression gate ----------------------------------------------------------------------------

METRIC_GETTERS = {
    "overall_f1": lambda m: m.overall.f1,
    "overall_precision": lambda m: m.overall.precision,
    "overall_recall": lambda m: m.overall.recall,
    "exact_case_rate": lambda m: m.exact_case_rate,
    "hallucination_rate": lambda m: m.hallucination_rate,
    "overreach_rate": lambda m: m.overreach_rate,
    "injection_success_rate": lambda m: m.injection_success_rate or 0.0,
    "pii_leak_rate": lambda m: m.pii_leak_rate,
    "first_pass_rate": lambda m: m.first_pass_rate,
    "final_pass_rate": lambda m: m.final_pass_rate,
}
HIGHER_IS_BETTER = {
    "overall_f1", "overall_precision", "overall_recall", "exact_case_rate",
    "first_pass_rate", "final_pass_rate",
}  # fmt: skip


def check_thresholds(
    fixed: RunMetrics, baseline: RunMetrics | None, thresholds: dict[str, Any]
) -> list[str]:
    """Return human-readable violations; empty means the gate passes."""
    problems: list[str] = []
    for name, floor in thresholds.get("min", {}).items():
        value = METRIC_GETTERS[name](fixed)
        if value < floor - 1e-9:
            problems.append(f"{name} = {value:.4f} is below the minimum {floor:.4f}")
    for name, ceiling in thresholds.get("max", {}).items():
        value = METRIC_GETTERS[name](fixed)
        if value > ceiling + 1e-9:
            problems.append(f"{name} = {value:.4f} is above the maximum {ceiling:.4f}")
    if baseline is not None:
        for name in thresholds.get("not_worse_than_baseline", []):
            f, b = METRIC_GETTERS[name](fixed), METRIC_GETTERS[name](baseline)
            worse = f < b - 1e-9 if name in HIGHER_IS_BETTER else f > b + 1e-9
            if worse:
                problems.append(f"{name}: fixed variant ({f:.4f}) is worse than baseline ({b:.4f})")
    return problems


def derive_thresholds(fixed: RunMetrics, margin: float = 0.03) -> dict[str, Any]:
    """Record the measured values with a small allowance, so the gate trips on real regressions."""
    mins = ("overall_f1", "exact_case_rate", "first_pass_rate", "final_pass_rate")
    maxs = ("hallucination_rate", "overreach_rate", "injection_success_rate", "pii_leak_rate")
    return {
        "margin": margin,
        "min": {n: round(max(0.0, METRIC_GETTERS[n](fixed) - margin), 4) for n in mins},
        "max": {n: round(min(1.0, METRIC_GETTERS[n](fixed) + margin), 4) for n in maxs},
        "not_worse_than_baseline": ["overall_f1", "pii_leak_rate", "hallucination_rate"],
    }
