"""Ports: the pipeline depends on these, never on a concrete SDK, broker or NLP library."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from cda_api.domain.redaction_map import RedactionMap
from pydantic import BaseModel


@dataclass(frozen=True)
class Message:
    role: str  # "user" | "assistant"
    content: str


@dataclass(frozen=True)
class Prompt:
    system: str
    messages: list[Message]
    version: str


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    retries: int = 0
    cost_usd: Decimal = Decimal("0")


class LLMError(Exception):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class LLMUnavailable(LLMError):
    """Raised after retries are exhausted or while the circuit breaker is open."""


class LLMProvider(Protocol):
    name: str

    async def generate_structured(
        self, prompt: Prompt, schema: type[BaseModel], **opts: Any
    ) -> LLMResult: ...


@dataclass(frozen=True)
class RedactionResult:
    text: str
    mapping: RedactionMap
    counts: dict[str, int] = field(default_factory=dict)


class Redactor(Protocol):
    def redact(self, text: str, language: str) -> RedactionResult: ...
