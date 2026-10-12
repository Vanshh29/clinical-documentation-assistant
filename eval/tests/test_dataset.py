from collections import Counter

from cda_eval.cases import CASES, FIELDS, LIST_FIELDS, TEXT_FIELDS
from cda_eval.metrics import key_matches


def test_dataset_is_large_enough_and_balanced() -> None:
    assert len(CASES) >= 30
    langs = Counter(c.language for c in CASES)
    assert langs["de"] >= 10 and langs["en"] >= 10
    assert {"clean", "messy", "missing", "contradictory", "injection"} <= {
        c.category for c in CASES
    }


def test_ids_are_unique() -> None:
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids))


def test_gold_has_every_field_in_the_right_shape() -> None:
    for c in CASES:
        assert set(c.gold) == set(FIELDS), c.id
        for name in TEXT_FIELDS:
            assert c.gold[name] is None or (c.gold[name] and all(c.gold[name])), (c.id, name)
        for name in LIST_FIELDS:
            assert isinstance(c.gold[name], list), (c.id, name)


def test_every_gold_key_is_grounded_in_the_note() -> None:
    """Gold must come from the note: a key that is not in the text can never be matched fairly."""
    for c in CASES:
        for name in FIELDS:
            for key in c.gold[name] or []:
                assert key_matches(key, c.text), f"{c.id}.{name}: {key!r} not in note"


def test_pii_strings_appear_verbatim_in_their_note() -> None:
    for c in CASES:
        for p in c.pii:
            assert p in c.text, f"{c.id}: {p!r}"


def test_forbidden_strings_are_attacker_text_not_clinical_content() -> None:
    injected = [c for c in CASES if c.category == "injection"]
    assert len(injected) >= 4 and all(c.forbidden for c in injected)
    for c in CASES:
        if c.forbidden and c.category != "injection":
            raise AssertionError(f"{c.id} has forbidden strings but is not an injection case")


def test_both_languages_have_undocumented_and_contradictory_cases() -> None:
    for lang in ("de", "en"):
        mine = [c for c in CASES if c.language == lang]
        assert any(c.gold["assessment"] is None for c in mine), lang
        assert any(c.category == "contradictory" for c in mine), lang


def test_synthetic_notes_contain_no_real_looking_domains() -> None:
    for c in CASES:
        assert "@" not in c.text or "example.org" in c.text, c.id
