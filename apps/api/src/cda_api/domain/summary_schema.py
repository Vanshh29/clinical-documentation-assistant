"""Versioned structured summary schema.

Every field carries a confidence and the source spans that support it. A field the note does
not document must be `value=None` with no spans; the model must never guess.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0"


class SourceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered(self) -> "SourceSpan":
        if self.end <= self.start:
            raise ValueError("source span end must be greater than start")
        return self


class Medication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    dose: str | None = None
    frequency: str | None = None


class SummaryField[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: T | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_spans: list[SourceSpan] = Field(default_factory=list)

    @model_validator(mode="after")
    def _undocumented_has_no_support(self) -> "SummaryField[T]":
        empty = self.value is None or self.value == [] or self.value == ""
        if empty and self.source_spans:
            raise ValueError("an undocumented field must not cite source spans")
        return self


class ClinicalSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = SCHEMA_VERSION  # type: ignore[assignment]
    chief_complaint: SummaryField[str]
    history_of_present_illness: SummaryField[str]
    medications: SummaryField[list[Medication]]
    allergies: SummaryField[list[str]]
    assessment: SummaryField[str]
    plan: SummaryField[str]
    follow_up_items: SummaryField[list[str]]


FIELD_NAMES: tuple[str, ...] = (
    "chief_complaint",
    "history_of_present_illness",
    "medications",
    "allergies",
    "assessment",
    "plan",
    "follow_up_items",
)


def spans_exist_in_text(summary: ClinicalSummary, text: str) -> list[str]:
    """Post-check: every cited span must match the (redacted) note exactly.

    Returns the names of fields that cite text the note does not contain.
    """
    bad: list[str] = []
    for name in FIELD_NAMES:
        field: SummaryField[object] = getattr(summary, name)
        for span in field.source_spans:
            if text[span.start : span.end] != span.text:
                bad.append(name)
                break
    return bad
