from cda_api.domain.summary_schema import ClinicalSummary, Medication, SourceSpan, SummaryField

NOTE_TEXT = (
    "Synthetic note. Patient presents with cough for three days. "
    "Takes ibuprofen 400 mg twice daily. No known allergies documented."
)


def span(text: str, source: str = NOTE_TEXT) -> SourceSpan:
    start = source.index(text)
    return SourceSpan(start=start, end=start + len(text), text=text)


def make_summary(chief: str | None = "cough for three days") -> ClinicalSummary:
    return ClinicalSummary(
        chief_complaint=SummaryField[str](
            value=chief,
            confidence=0.9,
            source_spans=[span("cough for three days")] if chief else [],
        ),
        history_of_present_illness=SummaryField[str](),
        medications=SummaryField[list[Medication]](
            value=[Medication(name="ibuprofen", dose="400 mg", frequency="twice daily")],
            confidence=0.8,
            source_spans=[span("ibuprofen 400 mg twice daily")],
        ),
        allergies=SummaryField[list[str]](),
        assessment=SummaryField[str](),
        plan=SummaryField[str](),
        follow_up_items=SummaryField[list[str]](),
    )
