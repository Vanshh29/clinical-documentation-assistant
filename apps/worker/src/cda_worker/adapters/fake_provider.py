# ruff: noqa: E501
"""Deterministic offline provider: a keyword/regex extractor that obeys the same contract as a
real model (verbatim quotes, null when undocumented). It makes the app and tests run with no API
key. It is intentionally simple; eval numbers for it measure the pipeline, not a language model."""

import re
import time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from cda_worker.domain.limits import estimate_tokens
from cda_worker.domain.ports import LLMResult, Prompt

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")
_NOTE = re.compile(r"<note>\n?(.*?)\n?</note>", re.DOTALL)

_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("allergies", re.compile(r"allerg", re.I)),
    (
        "follow_up_items",
        re.compile(
            r"follow[- ]?up|re-?check|return in|kontrolle|wiedervorstellung|nachsorge", re.I
        ),
    ),
    ("medications", re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:mg|mcg|µg|g|ml|ie)\b", re.I)),
    ("assessment", re.compile(r"assessment|impression|diagnos|beurteilung|verdacht|suspect", re.I)),
    ("plan", re.compile(r"\bplan\b|recommend|will start|prescrib|therapie|empfehl|verordn", re.I)),
    (
        "chief_complaint",
        re.compile(
            r"chief complaint|presents with|complains? of|beschwerden|klagt|stellt sich", re.I
        ),
    ),
    (
        "history_of_present_illness",
        re.compile(r"since|for \d+|seit|anamnese|began|begann|history", re.I),
    ),
]
_MED = re.compile(
    r"\b([A-Za-zÄÖÜäöüß][\wäöüß-]{2,})\s+(\d+(?:[.,]\d+)?\s?(?:mg|mcg|µg|g|ml|IE))"
    r"(?:\s+((?:once|twice|\d+x|\d-\d-\d)[\w\s-]{0,18}?(?:daily|täglich|per day|a day)?))?(?=[\s,.;]|$)",
)
_NO_ALLERGY = re.compile(r"no known allerg|keine bekannten allergien|nkda|keine allergien", re.I)


def _span(text: str) -> dict[str, str]:
    return {"text": text}


def _empty() -> dict[str, Any]:
    return {"value": None, "confidence": 0.0, "source_spans": []}


class FakeProvider:
    name = "fake"
    model = "fake-extractor-v1"

    async def generate_structured(
        self, prompt: Prompt, schema: type[BaseModel], **opts: Any
    ) -> LLMResult:
        started = time.perf_counter()
        match = _NOTE.search(prompt.messages[0].content)
        note = match.group(1) if match else ""
        data = self._extract(note)
        out_text = str(data)
        return LLMResult(
            data=data,
            model=self.model,
            input_tokens=estimate_tokens(prompt.system) + estimate_tokens(note),
            output_tokens=estimate_tokens(out_text),
            latency_ms=int((time.perf_counter() - started) * 1000),
            cost_usd=Decimal("0"),
        )

    def _extract(self, note: str) -> dict[str, Any]:
        buckets: dict[str, list[str]] = {name: [] for name, _ in _RULES}
        for sentence in (m.group(0).strip() for m in _SENTENCE.finditer(note)):
            if len(sentence) < 4:
                continue
            for name, pattern in _RULES:
                if pattern.search(sentence):
                    buckets[name].append(sentence)
                    break
        out: dict[str, Any] = {"schema_version": "1.0"}
        for name in (
            "chief_complaint", "history_of_present_illness", "medications", "allergies",
            "assessment", "plan", "follow_up_items",
        ):  # fmt: skip
            out[name] = _empty()
        out["chief_complaint"] = self._text_field(buckets["chief_complaint"][:1])
        out["history_of_present_illness"] = self._text_field(buckets["history_of_present_illness"])
        out["assessment"] = self._text_field(buckets["assessment"])
        out["plan"] = self._text_field(buckets["plan"])
        out["follow_up_items"] = self._list_field(buckets["follow_up_items"])
        out["allergies"] = self._allergy_field(buckets["allergies"])
        out["medications"] = self._med_field(buckets["medications"])
        return out

    @staticmethod
    def _text_field(sentences: list[str]) -> dict[str, Any]:
        if not sentences:
            return _empty()
        return {
            "value": " ".join(sentences),
            "confidence": 0.7,
            "source_spans": [_span(s) for s in sentences],
        }

    @staticmethod
    def _list_field(sentences: list[str]) -> dict[str, Any]:
        if not sentences:
            return _empty()
        return {
            "value": sentences,
            "confidence": 0.7,
            "source_spans": [_span(s) for s in sentences],
        }

    @staticmethod
    def _allergy_field(sentences: list[str]) -> dict[str, Any]:
        if not sentences:
            return _empty()
        values = ["no known allergies" if _NO_ALLERGY.search(s) else s for s in sentences]
        return {"value": values, "confidence": 0.7, "source_spans": [_span(s) for s in sentences]}

    @staticmethod
    def _med_field(sentences: list[str]) -> dict[str, Any]:
        meds: list[dict[str, str | None]] = []
        spans = []
        for sentence in sentences:
            found = list(_MED.finditer(sentence))
            for m in found:
                meds.append(
                    {
                        "name": m.group(1),
                        "dose": m.group(2),
                        "frequency": (m.group(3) or "").strip() or None,
                    }
                )
            if found:
                spans.append(_span(sentence))
        if not meds:
            return _empty()
        return {"value": meds, "confidence": 0.7, "source_spans": spans}
