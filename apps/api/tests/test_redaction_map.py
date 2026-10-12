import pytest
from cryptography.fernet import Fernet

from cda_api.adapters.crypto import MappingCipher
from cda_api.domain.errors import DomainError
from cda_api.domain.redaction_map import RedactionMap, Replacement

ORIGINAL = "Anna Schmidt has a cough. Call 0171 555."
REDACTED = "[PERSON_1] has a cough. Call [PHONE_1]."
MAP = RedactionMap(
    (
        Replacement("[PERSON_1]", "Anna Schmidt", 0, 10, 0, 12),
        Replacement("[PHONE_1]", "0171 555", 29, 38, 31, 39),
    )
)


def test_rehydrate_text_and_json_roundtrip() -> None:
    assert MAP.rehydrate_text(REDACTED) == ORIGINAL
    assert RedactionMap.from_json(MAP.to_json()) == MAP


@pytest.mark.parametrize("quote", ["has a cough", "[PERSON_1] has", "Call [PHONE_1]"])
def test_span_translation_covers_placeholders(quote: str) -> None:
    start = REDACTED.index(quote)
    o_start = MAP.to_original_offset(start, is_end=False)
    o_end = MAP.to_original_offset(start + len(quote), is_end=True)
    assert ORIGINAL[o_start:o_end] == MAP.rehydrate_text(quote)


def test_rehydrate_summary_translates_values_and_spans() -> None:
    quote = "[PERSON_1] has a cough."
    content = {
        "chief_complaint": {
            "value": quote,
            "confidence": 0.8,
            "source_spans": [{"start": 0, "end": len(quote), "text": quote}],
        },
        "medications": {
            "value": [{"name": "x", "dose": None, "frequency": None}],
            "source_spans": [],
        },
    }
    shown = MAP.rehydrate_summary(content, ORIGINAL)
    assert shown["chief_complaint"]["value"] == "Anna Schmidt has a cough."
    span = shown["chief_complaint"]["source_spans"][0]
    assert ORIGINAL[span["start"] : span["end"]] == span["text"] == "Anna Schmidt has a cough."
    assert shown["medications"]["value"][0]["name"] == "x"


def test_cipher_roundtrip_and_failure_modes() -> None:
    cipher = MappingCipher(Fernet.generate_key().decode())
    blob = cipher.encrypt(MAP)
    assert b"Schmidt" not in blob and cipher.decrypt(blob) == MAP
    with pytest.raises(DomainError):
        MappingCipher(Fernet.generate_key().decode()).decrypt(blob)  # wrong key
    with pytest.raises(DomainError):
        MappingCipher("")
