"""Schema the model fills in. It differs from the stored schema in one way: the model quotes
supporting text and the pipeline computes offsets, because models are unreliable at counting
characters."""

from cda_api.domain.summary_schema import (
    FIELD_NAMES,
    ClinicalSummary,
    Medication,
    SourceSpan,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class LlmSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1)


class LlmField[T](BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: T | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_spans: list[LlmSpan] = Field(default_factory=list)


class LlmSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1.0"
    chief_complaint: LlmField[str]
    history_of_present_illness: LlmField[str]
    medications: LlmField[list[Medication]]
    allergies: LlmField[list[str]]
    assessment: LlmField[str]
    plan: LlmField[str]
    follow_up_items: LlmField[list[str]]


def resolve_spans(llm: LlmSummary, note_text: str) -> tuple[ClinicalSummary | None, list[str]]:
    """Locate each quote in the note. Returns the stored-form summary, or the problems found."""
    problems: list[str] = []
    resolved: dict[str, dict[str, object]] = {}
    for name in FIELD_NAMES:
        field: LlmField[object] = getattr(llm, name)
        spans: list[SourceSpan] = []
        for quote in field.source_spans:
            start = note_text.find(quote.text)
            if start < 0:
                problems.append(f"{name}: quote not found verbatim in the note: {quote.text!r}")
                continue
            spans.append(SourceSpan(start=start, end=start + len(quote.text), text=quote.text))
        resolved[name] = {
            "value": field.value,
            "confidence": field.confidence,
            "source_spans": [s.model_dump() for s in spans],
        }
    if problems:
        return None, problems
    try:
        return ClinicalSummary.model_validate({"schema_version": "1.0", **resolved}), []
    except ValidationError as exc:
        return None, _describe(exc)


def _describe(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors(include_input=False)]


def describe_errors(exc: ValidationError) -> list[str]:
    return _describe(exc)
