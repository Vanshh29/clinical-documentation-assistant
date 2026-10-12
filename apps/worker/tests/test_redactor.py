import pytest
from cda_api.domain.redaction_map import RedactionMap

from cda_worker.adapters.redactor import PresidioRedactor, detect_language
from tests.pii_corpus import CASES

# Thresholds sit below the figures measured by scripts/pii_report.py (see docs/pii-redaction-report.md)
# so the suite fails on a real regression rather than on noise.
MIN_RECALL = 0.90
MIN_PRECISION = 0.80
MIN_RETENTION = 0.90


def test_language_detection() -> None:
    assert (
        detect_language(
            "Der Patient klagt seit drei Tagen über Husten und nimmt keine Medikamente."
        )
        == "de"
    )
    assert (
        detect_language("The patient reports cough for three days and takes no medication.") == "en"
    )


def test_placeholders_are_typed_and_numbered(redactor: PresidioRedactor) -> None:
    res = redactor.redact("Mr. John Carter saw Anna Schmidt. John Carter left.", "en")
    assert "John Carter" not in res.text and "Anna Schmidt" not in res.text
    assert res.text.count("[PERSON_1]") == 2  # same person, same placeholder
    assert "[PERSON_2]" in res.text


def test_clinical_durations_are_not_redacted(redactor: PresidioRedactor) -> None:
    res = redactor.redact("Husten seit drei Tagen, Fieber seit 2 Wochen. Cough for 3 days.", "auto")
    assert "drei Tagen" in res.text and "2 Wochen" in res.text and "3 days" in res.text


@pytest.mark.parametrize("lang,text,pii,keep", CASES)
def test_no_pii_leaks(
    redactor: PresidioRedactor, lang: str, text: str, pii: list[str], keep: list[str]
) -> None:
    res = redactor.redact(text, lang)
    assert [p for p in pii if p in res.text] == []


def test_aggregate_quality_gates(redactor: PresidioRedactor) -> None:
    total = caught = found = true_found = keep_total = keep_ok = 0
    for lang, text, pii, keep in CASES:
        res = redactor.redact(text, lang)
        total += len(pii)
        caught += sum(p not in res.text for p in pii)
        for r in res.mapping.replacements:
            found += 1
            true_found += any(r.original in p or p in r.original for p in pii)
        keep_total += len(keep)
        keep_ok += sum(k in res.text for k in keep)
    assert caught / total >= MIN_RECALL, f"recall {caught}/{total}"
    assert true_found / found >= MIN_PRECISION, f"precision {true_found}/{found}"
    assert keep_ok / keep_total >= MIN_RETENTION, f"retention {keep_ok}/{keep_total}"


def test_guard_keeps_drug_names_that_ner_mistakes_for_people() -> None:
    guarded = PresidioRedactor(guard_clinical_terms=True)
    text = "Patient nimmt Metformin 500 mg und Ramipril 5 mg."
    assert "Metformin 500 mg" in guarded.redact(text, "de").text
    assert "Ramipril 5 mg" in guarded.redact(text, "de").text


def test_map_roundtrip_restores_original(redactor: PresidioRedactor) -> None:
    text = "Patientin Anna Schmidt, geb. 03.04.1961, wohnt in München. Tel. +49 170 1234567."
    res = redactor.redact(text, "de")
    restored = RedactionMap.from_json(res.mapping.to_json()).rehydrate_text(res.text)
    assert restored == text


def test_span_offsets_translate_back_to_original(redactor: PresidioRedactor) -> None:
    text = "Heute: Anna Schmidt klagt über Husten. Plan: Hustensaft."
    res = redactor.redact(text, "de")
    quote = "klagt über Husten"
    start = res.text.index(quote)
    o_start = res.mapping.to_original_offset(start, is_end=False)
    o_end = res.mapping.to_original_offset(start + len(quote), is_end=True)
    assert text[o_start:o_end] == quote
    ph = res.mapping.replacements[0]
    whole = res.mapping.to_original_offset(ph.r_start + 2, is_end=False)
    assert whole == ph.o_start  # a span starting inside a placeholder snaps to the entity
