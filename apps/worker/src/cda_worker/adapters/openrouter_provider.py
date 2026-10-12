"""LLM provider for OpenRouter's chat-completions API.

Exponential backoff with full jitter on 429/5xx and transport errors, bounded retries, timeouts.
Never logs prompts or note text.
"""

import asyncio
import json
import logging
import random
import re
import time
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel

from cda_worker.domain.ports import LLMError, LLMResult, LLMUnavailable, Prompt

log = logging.getLogger("cda.worker.llm")

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class OpenRouterProvider:
    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        backoff_cap: float = 20.0,
        price_in_per_mtok: Decimal = Decimal("0"),
        price_out_per_mtok: Decimal = Decimal("0"),
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for the openrouter provider")
        self._model = model
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._max_retries = max_retries
        self._base, self._cap = backoff_base, backoff_cap
        self._price_in, self._price_out = price_in_per_mtok, price_out_per_mtok
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._sleep = sleep

    def _body(self, prompt: Prompt, schema: type[BaseModel]) -> dict[str, Any]:
        return {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": prompt.system},
                *({"role": m.role, "content": m.content} for m in prompt.messages),
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": False,
                    "schema": schema.model_json_schema(),
                },
            },
            "usage": {"include": True},
        }

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after and retry_after.isdigit():
            return min(float(retry_after), self._cap)
        return random.uniform(0, min(self._cap, self._base * 2**attempt))

    async def generate_structured(
        self, prompt: Prompt, schema: type[BaseModel], **opts: Any
    ) -> LLMResult:
        body = self._body(prompt, schema)
        started = time.perf_counter()
        attempts = 0
        while True:
            retry_after: str | None = None
            try:
                response = await self._client.post(self._url, headers=self._headers, json=body)
                if response.status_code == 200:
                    return self._parse(response, started, attempts)
                if response.status_code not in RETRYABLE_STATUS:
                    raise LLMError(f"request rejected with status {response.status_code}")
                retry_after = response.headers.get("retry-after")
                reason = f"status {response.status_code}"
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                reason = type(exc).__name__
            if attempts >= self._max_retries:
                raise LLMUnavailable(
                    f"gave up after {attempts + 1} attempts ({reason})", retryable=True
                )
            delay = self._delay(attempts, retry_after)
            attempts += 1
            log.warning(
                "llm call failed, retrying",
                extra={"ctx": {"reason": reason, "retry": attempts, "delay_s": round(delay, 2)}},
            )
            await self._sleep(delay)

    def _parse(self, response: httpx.Response, started: float, retries: int) -> LLMResult:
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            data = json.loads(_FENCE.sub("", content.strip()))
            if not isinstance(data, dict):
                raise ValueError("model output is not a JSON object")
        except (KeyError, IndexError, ValueError, TypeError):
            # Malformed output is handed to the validation loop as an empty object so the
            # model gets a chance to correct itself instead of failing the whole note.
            data, payload = {}, locals().get("payload", {}) or {}
        usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))
        if "cost" in usage:
            cost = Decimal(str(usage["cost"]))
        else:
            cost = (self._price_in * tokens_in + self._price_out * tokens_out) / Decimal(1_000_000)
        return LLMResult(
            data=data,
            model=str(payload.get("model", self._model))
            if isinstance(payload, dict)
            else self._model,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            latency_ms=int((time.perf_counter() - started) * 1000),
            retries=retries,
            cost_usd=cost,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
