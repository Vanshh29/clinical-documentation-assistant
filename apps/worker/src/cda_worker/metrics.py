from prometheus_client import Counter, Histogram

NOTES = Counter("cda_worker_notes_total", "Notes handled by the worker", ["outcome"])
DURATION = Histogram(
    "cda_worker_note_duration_seconds",
    "Time to process one note (redaction + model + validation)",
    buckets=(0.05, 0.25, 0.5, 1, 2.5, 5, 10, 20, 40, 80),
)
LLM_TOKENS = Counter("cda_worker_llm_tokens_total", "Model tokens used", ["direction"])
LLM_COST = Counter("cda_worker_llm_cost_usd_total", "Estimated model spend in USD")
LLM_RETRIES = Counter("cda_worker_llm_validation_retries_total", "Re-asks after invalid output")
REDACTIONS = Counter("cda_worker_redactions_total", "Personal-data spans replaced", ["type"])
