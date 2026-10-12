from cryptography.fernet import Fernet, InvalidToken

from cda_api.domain.errors import DomainError
from cda_api.domain.redaction_map import RedactionMap


class MappingCipher:
    """Application-level encryption for the placeholder map (separate from the LLM payload)."""

    def __init__(self, key: str) -> None:
        if not key:
            raise DomainError("PII_ENCRYPTION_KEY is not configured")
        self._fernet = Fernet(key.encode())

    def encrypt(self, mapping: RedactionMap) -> bytes:
        return self._fernet.encrypt(mapping.to_json().encode())

    def decrypt(self, ciphertext: bytes) -> RedactionMap:
        try:
            return RedactionMap.from_json(self._fernet.decrypt(ciphertext).decode())
        except InvalidToken as exc:
            raise DomainError("placeholder map could not be decrypted") from exc
