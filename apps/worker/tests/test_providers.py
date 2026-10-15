import json
from decimal import Decimal
from typing import Any

import httpx
import pytest

from cda_worker.adapters.circuit_breaker import CircuitBreakerProvider
from cda_worker.adapters.openrouter_provider import OpenRouterProvider
from cda_worker.domain.llm_output import LlmSummary
from cda_worker.domain.ports import LLMError, LLMResult, LLMUnavailable, Message, Prompt

PROMPT = Prompt("sys", [Message("user", "hello")], "v1")


def ok_response(content: str = '{"a": 1}', **extra: Any) -> httpx.Response:
    body = {
        "model": "vendor/model-x",
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30, **extra},
    }
    return httpx.Response(200, json=body)


def provider(handler: Any, sleeps: list[float], **kw: Any) -> OpenRouterProvider:
    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    return OpenRouterProvider(
        "test-key",
        "vendor/model-x",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        sleep=fake_sleep,
        **kw,
    )


async def test_success_parses_fenced_json_usage_and_cost() -> None:
    p = provider(lambda r: ok_response('```json\n{"a": 1}\n```', cost=0.0042), [])
    res = await p.generate_structured(PROMPT, LlmSummary)
    assert res.data == {"a": 1}
    assert (res.input_tokens, res.output_tokens) == (120, 30)
    assert res.cost_usd == Decimal("0.0042") and res.model == "vendor/model-x"


async def test_cost_falls_back_to_configured_prices() -> None:
    p = provider(
        lambda r: ok_response(),
        [],
        price_in_per_mtok=Decimal("1"),
        price_out_per_mtok=Decimal("2"),
    )
    res = await p.generate_structured(PROMPT, LlmSummary)
    assert res.cost_usd == Decimal("0.00018")  # (120*1 + 30*2) / 1e6


async def test_request_carries_schema_auth_and_no_secrets_in_body() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.read().decode()
        return ok_response()

    await provider(handler, []).generate_structured(PROMPT, LlmSummary)
    assert seen["auth"] == "Bearer test-key"
    assert "json_schema" in seen["body"] and "test-key" not in seen["body"]


async def test_request_caps_output_tokens_so_the_api_does_not_reserve_the_model_maximum() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return ok_response()

    await provider(handler, []).generate_structured(PROMPT, LlmSummary)
    await provider(handler, [], max_output_tokens=1234).generate_structured(PROMPT, LlmSummary)
    assert [b["max_tokens"] for b in seen] == [8000, 1234]


async def test_retries_429_and_5xx_with_backoff_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "3"})
        if calls["n"] == 2:
            return httpx.Response(503)
        return ok_response()

    sleeps: list[float] = []
    res = await provider(handler, sleeps).generate_structured(PROMPT, LlmSummary)
    assert calls["n"] == 3 and res.retries == 2
    assert sleeps[0] == 3.0  # honours Retry-After
    assert 0 <= sleeps[1] <= 2.0  # jittered exponential window for attempt 1


async def test_gives_up_after_max_retries() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500)

    with pytest.raises(LLMUnavailable):
        await provider(handler, [], max_retries=2).generate_structured(PROMPT, LlmSummary)
    assert calls["n"] == 3


async def test_timeouts_are_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ReadTimeout("slow", request=request)
        return ok_response()

    res = await provider(handler, []).generate_structured(PROMPT, LlmSummary)
    assert calls["n"] == 2 and res.data == {"a": 1}


async def test_client_errors_are_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401)

    with pytest.raises(LLMError) as err:
        await provider(handler, []).generate_structured(PROMPT, LlmSummary)
    assert calls["n"] == 1 and not isinstance(err.value, LLMUnavailable)


async def test_null_content_becomes_empty_object_instead_of_crashing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "model": "vendor/model-x",
            "choices": [{"finish_reason": "length", "message": {"content": None}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 8000},
        }
        return httpx.Response(200, json=body)

    res = await provider(handler, []).generate_structured(PROMPT, LlmSummary)
    assert res.data == {} and res.output_tokens == 8000


async def test_malformed_model_output_becomes_empty_object_for_validation_loop() -> None:
    res = await provider(lambda r: ok_response("sorry, I cannot do that"), []).generate_structured(
        PROMPT, LlmSummary
    )
    assert res.data == {}


def test_api_key_is_required() -> None:
    with pytest.raises(ValueError):
        OpenRouterProvider("", "m")


class Flaky:
    name = "flaky"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = True

    async def generate_structured(self, prompt: Prompt, schema: Any, **opts: Any) -> LLMResult:
        self.calls += 1
        if self.fail:
            raise LLMUnavailable("down", retryable=True)
        return LLMResult({}, "m", 1, 1, 1)


async def test_circuit_opens_then_recovers_after_reset_window() -> None:
    now = {"t": 0.0}
    inner = Flaky()
    cb = CircuitBreakerProvider(
        inner, failure_threshold=2, reset_seconds=30, clock=lambda: now["t"]
    )
    for _ in range(2):
        with pytest.raises(LLMUnavailable):
            await cb.generate_structured(PROMPT, LlmSummary)
    assert cb.is_open
    with pytest.raises(LLMUnavailable, match="circuit open"):
        await cb.generate_structured(PROMPT, LlmSummary)
    assert inner.calls == 2  # the third call never reached the provider
    now["t"] = 31.0
    inner.fail = False
    assert (await cb.generate_structured(PROMPT, LlmSummary)).model == "m"
    assert not cb.is_open


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (402, "llm_credits_exhausted"),
        (401, "llm_auth_failed"),
        (403, "llm_auth_failed"),
        (400, "llm_request_rejected"),
    ],
)
async def test_rejections_carry_an_actionable_reason(status: int, code: str) -> None:
    with pytest.raises(LLMError) as err:
        await provider(lambda r: httpx.Response(status), []).generate_structured(PROMPT, LlmSummary)
    assert err.value.code == code and not err.value.retryable
