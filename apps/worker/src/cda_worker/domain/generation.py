"""Validate-and-retry loop around an LLMProvider. Pure orchestration: no DB, no Kafka."""

from dataclasses import dataclass
from decimal import Decimal

from cda_api.domain.summary_schema import ClinicalSummary, spans_exist_in_text
from pydantic import ValidationError

from cda_worker.domain.llm_output import LlmSummary, describe_errors, resolve_spans
from cda_worker.domain.ports import LLMError, LLMProvider, LLMUnavailable
from cda_worker.domain.prompts import PromptBuilder

FAILURE_VALIDATION = "schema_validation_failed"
FAILURE_UNAVAILABLE = "llm_unavailable"
FAILURE_REJECTED = "llm_request_rejected"


@dataclass
class GenerationOutcome:
    summary: ClinicalSummary | None
    failure_reason: str | None
    model: str
    prompt_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    retries: int = 0
    cost_usd: Decimal = Decimal("0")


async def generate_validated(
    provider: LLMProvider,
    builder: PromptBuilder,
    note_text: str,
    *,
    max_validation_retries: int,
    model_name: str,
) -> GenerationOutcome:
    """Call the model; on invalid output feed the errors back, up to a bounded number of times."""
    out = GenerationOutcome(None, None, model_name, builder.version)
    feedback: list[str] | None = None
    for attempt in range(max_validation_retries + 1):
        out.retries = attempt
        try:
            result = await provider.generate_structured(
                builder.build(note_text, feedback), LlmSummary
            )
        except LLMUnavailable:
            out.failure_reason = FAILURE_UNAVAILABLE
            return out
        except LLMError:
            out.failure_reason = FAILURE_REJECTED
            return out
        out.model = result.model
        out.input_tokens += result.input_tokens
        out.output_tokens += result.output_tokens
        out.latency_ms += result.latency_ms
        out.cost_usd += result.cost_usd

        summary, problems = _validate(result.data, note_text)
        if summary is not None:
            out.summary = summary
            return out
        feedback = problems
    out.failure_reason = FAILURE_VALIDATION
    return out


def _validate(data: dict[str, object], note_text: str) -> tuple[ClinicalSummary | None, list[str]]:
    try:
        llm = LlmSummary.model_validate(data)
    except ValidationError as exc:
        return None, describe_errors(exc)
    summary, problems = resolve_spans(llm, note_text)
    if summary is None:
        return None, problems
    bad = spans_exist_in_text(summary, note_text)  # defensive post-check required by the spec
    if bad:
        return None, [f"{name}: a cited span does not match the note" for name in bad]
    return summary, []
