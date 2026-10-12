"""Placeholder map produced by redaction, and the reverse mapping used for display only."""

import json
from dataclasses import asdict, dataclass
from typing import Any

from cda_api.domain.summary_schema import FIELD_NAMES


@dataclass(frozen=True)
class Replacement:
    placeholder: str
    original: str
    r_start: int  # offsets in the redacted text
    r_end: int
    o_start: int  # offsets in the original text
    o_end: int


@dataclass(frozen=True)
class RedactionMap:
    replacements: tuple[Replacement, ...]

    def to_json(self) -> str:
        return json.dumps([asdict(r) for r in self.replacements])

    @classmethod
    def from_json(cls, raw: str) -> "RedactionMap":
        return cls(tuple(Replacement(**item) for item in json.loads(raw)))

    def rehydrate_text(self, text: str) -> str:
        lookup = {r.placeholder: r.original for r in self.replacements}
        for placeholder in sorted(lookup, key=len, reverse=True):
            text = text.replace(placeholder, lookup[placeholder])
        return text

    def to_original_offset(self, pos: int, *, is_end: bool) -> int:
        """Translate a redacted-text offset to the original text; spans snap to whole entities."""
        delta = 0
        for r in sorted(self.replacements, key=lambda x: x.r_start):
            if pos >= r.r_end:
                delta += (r.o_end - r.o_start) - (r.r_end - r.r_start)
            elif pos > r.r_start:
                return r.o_end if is_end else r.o_start
            else:
                break
        return pos + delta

    def _rehydrate_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.rehydrate_text(value)
        if isinstance(value, list):
            return [self._rehydrate_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._rehydrate_value(v) for k, v in value.items()}
        return value

    def rehydrate_summary(self, content: dict[str, Any], original_text: str) -> dict[str, Any]:
        """Restore real values and original-text span offsets. For display in the review UI only."""
        out = dict(content)
        for name in FIELD_NAMES:
            field = content.get(name)
            if not field:
                continue
            spans = []
            for span in field.get("source_spans", []):
                start = self.to_original_offset(span["start"], is_end=False)
                end = self.to_original_offset(span["end"], is_end=True)
                spans.append({"start": start, "end": end, "text": original_text[start:end]})
            out[name] = {
                **field,
                "value": self._rehydrate_value(field.get("value")),
                "source_spans": spans,
            }
        return out
