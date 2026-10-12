import asyncio

from cda_worker.adapters.fake_provider import FakeProvider

from cda_eval.cases import CASES
from cda_eval.report import dataset_fingerprint, render, summary_dict
from cda_eval.runner import VARIANTS, check_thresholds, derive_thresholds, run_variant


def run(variant: str, limit: int = 8):
    metrics, _ = asyncio.run(run_variant(VARIANTS[variant], CASES[:limit], FakeProvider(), "fake"))
    return metrics


def test_derived_thresholds_pass_on_the_run_they_came_from() -> None:
    fixed, base = run("fixed"), run("baseline")
    assert check_thresholds(fixed, base, derive_thresholds(fixed)) == []


def test_gate_trips_on_each_kind_of_regression() -> None:
    fixed, base = run("fixed"), run("baseline")
    t = derive_thresholds(fixed, margin=0.0)
    fixed.overall.tp -= 3  # fewer correct fields
    fixed.pii_leak_rate = 0.2
    fixed.hallucination_rate = base.hallucination_rate + 0.3
    problems = " | ".join(check_thresholds(fixed, base, t))
    assert "overall_f1" in problems and "below the minimum" in problems
    assert "pii_leak_rate" in problems and "above the maximum" in problems
    assert "worse than baseline" in problems


def test_run_is_deterministic_with_the_fake_provider() -> None:
    a, b = summary_dict(run("fixed")), summary_dict(run("fixed"))
    for key in ("overall_f1", "hallucination_rate", "pii_leak_rate", "exact_case_rate"):
        assert a[key] == b[key]


def test_guard_variant_is_not_worse_than_baseline_on_clinical_terms() -> None:
    fixed, base = run("fixed", 16), run("baseline", 16)
    assert fixed.overall.f1 >= base.overall.f1


def test_report_contains_headline_table_and_the_fake_provider_warning() -> None:
    results = {"baseline": run("baseline"), "fixed": run("fixed")}
    text = render(results, provider="fake", model="fake-extractor-v1", command="make eval", limit=8)
    assert "## Headline metrics" in text and "Read this first" in text
    assert "Field F1" in text and dataset_fingerprint() in text
    assert "PII leak rate after redaction" in text


def test_dataset_fingerprint_is_stable() -> None:
    assert dataset_fingerprint() == dataset_fingerprint() and len(dataset_fingerprint()) == 12
