import pytest
from pydantic import ValidationError

from cda_api.domain.diff import summary_diff
from cda_api.domain.enums import NoteStatus
from cda_api.domain.errors import InvalidTransition
from cda_api.domain.state_machine import can_transition, ensure_transition
from cda_api.domain.summary_schema import (
    ClinicalSummary,
    SourceSpan,
    SummaryField,
    spans_exist_in_text,
)
from tests.factories import NOTE_TEXT, make_summary, span

S = NoteStatus


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.SUBMITTED, S.PROCESSING),
        (S.PROCESSING, S.PENDING_REVIEW),
        (S.PROCESSING, S.FAILED_VALIDATION),
        (S.PENDING_REVIEW, S.APPROVED),
        (S.PENDING_REVIEW, S.REJECTED),
        (S.PENDING_REVIEW, S.SUBMITTED),
        (S.FAILED_VALIDATION, S.SUBMITTED),
    ],
)
def test_allowed_transitions(current: NoteStatus, target: NoteStatus) -> None:
    assert ensure_transition(current, target) == target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.SUBMITTED, S.APPROVED),
        (S.PROCESSING, S.APPROVED),
        (S.APPROVED, S.SUBMITTED),
        (S.REJECTED, S.APPROVED),
        (S.FAILED_VALIDATION, S.APPROVED),
    ],
)
def test_forbidden_transitions(current: NoteStatus, target: NoteStatus) -> None:
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransition):
        ensure_transition(current, target)


def test_undocumented_field_cannot_cite_spans() -> None:
    with pytest.raises(ValidationError):
        SummaryField[str](value=None, source_spans=[span("cough")])


def test_unknown_fields_are_rejected() -> None:
    data = make_summary().model_dump()
    data["diagnosis_guess"] = "pneumonia"
    with pytest.raises(ValidationError):
        ClinicalSummary.model_validate(data)


def test_span_end_must_follow_start() -> None:
    with pytest.raises(ValidationError):
        SourceSpan(start=5, end=5, text="x")


def test_span_postcheck_flags_fabricated_quote() -> None:
    summary = make_summary()
    assert spans_exist_in_text(summary, NOTE_TEXT) == []
    summary.chief_complaint.source_spans[0].text = "chest pain"
    assert spans_exist_in_text(summary, NOTE_TEXT) == ["chief_complaint"]


def test_diff_zero_when_unchanged() -> None:
    dumped = make_summary().model_dump(mode="json")
    result = summary_diff(dumped, dumped)
    assert result == {"changed_fields": {}, "edit_ratio": 0.0}


def test_diff_reports_changed_fields_and_ratio() -> None:
    before = make_summary().model_dump(mode="json")
    after = make_summary("persistent dry cough").model_dump(mode="json")
    result = summary_diff(before, after)
    assert list(result["changed_fields"]) == ["chief_complaint"]
    assert 0 < result["edit_ratio"] < 1


def test_an_explicit_none_may_cite_the_sentence_that_says_so() -> None:
    field = SummaryField[list[str]](
        value=[], confidence=0.9, source_spans=[span("ibuprofen 400 mg")]
    )
    assert field.value == [] and len(field.source_spans) == 1


def test_an_empty_string_still_counts_as_not_mentioned() -> None:
    with pytest.raises(ValidationError):
        SummaryField[str](value="", source_spans=[span("cough")])
