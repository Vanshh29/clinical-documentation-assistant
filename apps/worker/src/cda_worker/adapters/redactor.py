# ruff: noqa: E501
"""PII redaction with Microsoft Presidio (spaCy NER for names/places) plus regex recognizers
for German and international formats. Dates of clinical relevance ("three days", "seit 2 Wochen")
are deliberately NOT redacted: only calendar dates and dates of birth are."""

import re
from collections import defaultdict
from collections.abc import Iterable

from cda_api.domain.redaction_map import RedactionMap, Replacement
from presidio_analyzer import (
    AnalyzerEngine,
    EntityRecognizer,
    RecognizerRegistry,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import NlpArtifacts, NlpEngineProvider
from presidio_analyzer.predefined_recognizers import SpacyRecognizer

from cda_worker.domain.ports import RedactionResult

LANGUAGES = ("en", "de")
SPACY_MODELS = {"en": "en_core_web_sm", "de": "de_core_news_sm"}

# Presidio entity -> placeholder type
PLACEHOLDER_TYPE = {
    "PERSON": "PERSON",
    "LOCATION": "LOCATION",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "IBAN_CODE": "IBAN",
    "DE_INSURANCE_NUMBER": "INSURANCE_ID",
    "DATE_OF_BIRTH": "DOB",
    "DATE": "DATE",
}

_DOB_LABEL = r"(?:geb(?:oren)?\.?(?:\s+am)?|geburtsdatum|DOB|date\s+of\s+birth|born(?:\s+on)?)"
_DATE_NUMERIC = r"\d{1,2}[./-]\d{1,2}[./-](?:\d{4}|\d{2})"
_MONTHS_DE = (
    r"(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
)
_MONTHS_EN = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
)

# (entity, [(regex, score)], capture group, flags)
_PATTERNS: list[tuple[str, list[tuple[str, float]], int, int]] = [
    (
        "EMAIL_ADDRESS",
        [(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", 0.95)],
        0,
        0,
    ),
    (
        "IBAN_CODE",
        [(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b", 0.9)],
        0,
        0,
    ),
    (
        # Krankenversichertennummer: one letter followed by nine digits
        "DE_INSURANCE_NUMBER",
        [(r"\b[A-Z]\d{9}\b", 0.85)],
        0,
        0,
    ),
    (
        "PHONE_NUMBER",
        [
            (r"(?<!\w)(?:\+|00)\d{2}[\s/-]?\(?\d{2,5}\)?[\s/-]?\d{3,}(?:[\s/-]?\d{2,})*", 0.85),
            (r"(?<!\w)0\d{2,5}[\s/-]\d{3,}(?:[\s/-]?\d{2,})*", 0.8),
            (r"(?<!\w)\(\d{3}\)\s?\d{3}[-\s]\d{4}\b", 0.85),
            (r"(?<!\w)\d{3}[-.]\d{3}[-.]\d{4}\b", 0.8),
        ],
        0,
        0,
    ),
    (
        "DATE_OF_BIRTH",
        [
            (rf"{_DOB_LABEL}\s*:?\s*({_DATE_NUMERIC})", 0.95),
            (rf"{_DOB_LABEL}\s*:?\s*(\d{{1,2}}\.?\s+{_MONTHS_DE}\s+\d{{4}})", 0.95),
            (rf"{_DOB_LABEL}\s*:?\s*({_MONTHS_EN}\s+\d{{1,2}},?\s+\d{{4}})", 0.95),
            (rf"{_DOB_LABEL}\s*:?\s*(\d{{1,2}}\s+{_MONTHS_EN}\s+\d{{4}})", 0.95),
        ],
        1,
        re.IGNORECASE,
    ),
    (
        "DATE",
        [
            (rf"\b{_DATE_NUMERIC}\b", 0.7),
            (r"\b\d{4}-\d{2}-\d{2}\b", 0.8),
            (rf"\b\d{{1,2}}\.?\s+{_MONTHS_DE}(?:\s+\d{{4}})?", 0.8),
            (rf"\b{_MONTHS_EN}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?", 0.8),
            (rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTHS_EN}(?:\s+\d{{4}})?", 0.8),
        ],
        0,
        re.IGNORECASE,
    ),
]


class RegexRecognizer(EntityRecognizer):
    def __init__(
        self,
        entity: str,
        patterns: list[tuple[str, float]],
        language: str,
        group: int = 0,
        flags: int = 0,
    ) -> None:
        self._compiled = [(re.compile(p, flags), score) for p, score in patterns]
        self._group = group
        super().__init__(
            supported_entities=[entity],
            supported_language=language,
            name=f"{entity}_{language}_regex",
        )
        self._entity = entity

    def load(self) -> None:  # nothing to load
        return None

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        results = []
        for regex, score in self._compiled:
            for match in regex.finditer(text):
                start, end = match.span(self._group)
                if start >= 0 and end > start:
                    results.append(RecognizerResult(self._entity, start, end, score))
        return results


_DE_WORDS = frozenset(
    [
        "der",
        "die",
        "das",
        "und",
        "ist",
        "nicht",
        "mit",
        "seit",
        "von",
        "bei",
        "auf",
        "für",
        "wurde",
        "hat",
        "patient",
        "patientin",
        "klagt",
        "über",
        "nimmt",
        "keine",
        "kein",
        "wegen",
        "zur",
        "zum",
        "eine",
        "einen",
        "sich",
        "wird",
        "sind",
        "war",
    ]
)
_EN_WORDS = frozenset(
    [
        "the",
        "and",
        "is",
        "not",
        "with",
        "since",
        "of",
        "at",
        "on",
        "for",
        "was",
        "has",
        "patient",
        "reports",
        "takes",
        "no",
        "an",
        "a",
        "to",
        "be",
        "were",
        "this",
        "that",
        "which",
        "from",
        "denies",
        "complains",
    ]
)


def detect_language(text: str) -> str:
    words = re.findall(r"[a-zäöüß]+", text.lower())
    de = sum(w in _DE_WORDS for w in words)
    en = sum(w in _EN_WORDS for w in words)
    return "de" if de > en else "en"


class PresidioRedactor:
    def __init__(self, score_threshold: float = 0.5, guard_clinical_terms: bool = True) -> None:
        self._guard = guard_clinical_terms
        nlp = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [
                    {"lang_code": lang, "model_name": SPACY_MODELS[lang]} for lang in LANGUAGES
                ],
            }
        ).create_engine()
        registry = RecognizerRegistry(supported_languages=list(LANGUAGES))
        for lang in LANGUAGES:
            registry.add_recognizer(
                SpacyRecognizer(
                    supported_language=lang,
                    supported_entities=["PERSON", "LOCATION"],
                    ner_strength=0.85,
                )
            )
            for entity, patterns, group, flags in _PATTERNS:
                registry.add_recognizer(RegexRecognizer(entity, patterns, lang, group, flags))
        self._analyzer = AnalyzerEngine(
            nlp_engine=nlp, registry=registry, supported_languages=list(LANGUAGES)
        )
        self._entities = list(PLACEHOLDER_TYPE)
        self._threshold = score_threshold

    def find(self, text: str, language: str) -> list[RecognizerResult]:
        lang = detect_language(text) if language == "auto" else language
        raw = self._analyzer.analyze(
            text=text, language=lang, entities=self._entities, score_threshold=self._threshold
        )
        kept = _resolve_overlaps(raw)
        if self._guard:
            kept = [r for r in kept if not _is_clinical_term(text, r)]
        return kept

    def redact(self, text: str, language: str) -> RedactionResult:
        found = self.find(text, language)
        numbering: dict[str, int] = defaultdict(int)
        seen: dict[tuple[str, str], str] = {}
        replacements: list[Replacement] = []
        parts: list[str] = []
        cursor = 0
        redacted_len = 0
        counts: dict[str, int] = defaultdict(int)
        for hit in sorted(found, key=lambda r: r.start):
            original = text[hit.start : hit.end]
            kind = PLACEHOLDER_TYPE[hit.entity_type]
            key = (kind, " ".join(original.lower().split()))
            if key not in seen:
                numbering[kind] += 1
                seen[key] = f"[{kind}_{numbering[kind]}]"
            placeholder = seen[key]
            counts[kind] += 1
            gap = text[cursor : hit.start]
            parts.append(gap)
            redacted_len += len(gap)
            parts.append(placeholder)
            replacements.append(
                Replacement(
                    placeholder=placeholder,
                    original=original,
                    r_start=redacted_len,
                    r_end=redacted_len + len(placeholder),
                    o_start=hit.start,
                    o_end=hit.end,
                )
            )
            redacted_len += len(placeholder)
            cursor = hit.end
        parts.append(text[cursor:])
        return RedactionResult("".join(parts), RedactionMap(tuple(replacements)), dict(counts))


# Small NER models tag drug names as people ("Metformin 500 mg"). Redacting them would strip the
# clinical content the summary depends on, so name-like hits that look like drugs are kept.
_DOSE_AFTER = re.compile(r"\s*\d+(?:[.,]\d+)?\s?(?:mg|mcg|µg|g|ml|ie)\b", re.IGNORECASE)
_DRUG_SUFFIX = re.compile(
    r"(?:formin|pril|sartan|olol|statin|cillin|mycin|azol|profen|oxacin|prazol|dipin|gliptin|"
    r"parin|xaban|azepam|triptan|thiazid|semid|setron|terol|coxib|fenac|dronat|glitazon)$",
    re.IGNORECASE,
)


# Common nouns the small German model mistakes for names (symptom compounds, form labels).
_SYMPTOM_NOUN = re.compile(
    r"(?:schmerz(?:en)?|druck|husten|fieber|übelkeit|schwindel|atemnot)$", re.IGNORECASE
)
_LABELS = frozenset(
    {"kontakt", "tel", "tel.", "telefon", "termin", "email", "e-mail", "patient", "patientin",
     "befund", "anamnese", "diagnose", "therapie", "medikation", "allergie", "allergien"}
)  # fmt: skip


def _is_clinical_term(text: str, hit: RecognizerResult) -> bool:
    if hit.entity_type not in ("PERSON", "LOCATION"):
        return False
    surface = text[hit.start : hit.end]
    followed_by_dose = bool(_DOSE_AFTER.match(text, hit.end))
    single_token = " " not in surface
    looks_like_drug = single_token and bool(_DRUG_SUFFIX.search(surface))
    common_noun = single_token and (
        bool(_SYMPTOM_NOUN.search(surface)) or surface.lower() in _LABELS
    )
    return followed_by_dose or looks_like_drug or common_noun


def _resolve_overlaps(results: Iterable[RecognizerResult]) -> list[RecognizerResult]:
    """Keep the strongest, then longest, span wherever recognizers overlap."""
    ordered = sorted(results, key=lambda r: (-r.score, -(r.end - r.start), r.start))
    kept: list[RecognizerResult] = []
    for cand in ordered:
        if all(cand.end <= k.start or cand.start >= k.end for k in kept):
            kept.append(cand)
    return sorted(kept, key=lambda r: r.start)
