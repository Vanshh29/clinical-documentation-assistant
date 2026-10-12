"""Input size control.

Strategy (documented in docs/adr/ADR-004): tokens are estimated at ~4 characters each (no
tokenizer dependency). A note over the limit is truncated at the last sentence boundary inside
the budget. Truncation keeps a prefix, so source-span offsets remain valid, and the audit entry
records `truncated=true` so reviewers know the tail was not summarized.
"""

import math

CHARS_PER_TOKEN = 4
PROMPT_OVERHEAD_TOKENS = 700  # system prompt, instructions, schema


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def truncate_to_budget(text: str, max_input_tokens: int) -> tuple[str, bool]:
    budget_chars = max(0, max_input_tokens - PROMPT_OVERHEAD_TOKENS) * CHARS_PER_TOKEN
    if len(text) <= budget_chars:
        return text, False
    cut = text[:budget_chars]
    boundary = max(cut.rfind(". "), cut.rfind(".\n"), cut.rfind("\n\n"))
    if boundary > budget_chars // 2:
        cut = cut[: boundary + 1]
    return cut, True
