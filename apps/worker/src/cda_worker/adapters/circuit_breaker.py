import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from cda_worker.domain.ports import LLMProvider, LLMResult, LLMUnavailable, Prompt


class CircuitBreakerProvider:
    """Fail fast after repeated outages so a down provider does not stall the whole queue."""

    def __init__(
        self,
        inner: LLMProvider,
        *,
        failure_threshold: int = 5,
        reset_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self.name = inner.name
        self._threshold = failure_threshold
        self._reset = reset_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        return self._opened_at is not None and self._clock() - self._opened_at < self._reset

    async def generate_structured(
        self, prompt: Prompt, schema: type[BaseModel], **opts: Any
    ) -> LLMResult:
        if self.is_open:
            raise LLMUnavailable("circuit open", retryable=True)
        try:
            result = await self._inner.generate_structured(prompt, schema, **opts)
        except LLMUnavailable:
            self._failures += 1
            if self._failures >= self._threshold:
                self._opened_at = self._clock()  # half-open after the reset window
            raise
        self._failures = 0
        self._opened_at = None
        return result
