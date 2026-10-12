from decimal import Decimal
from typing import Any

from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cda_api.adapters.db.models import LlmCall, Note, Summary


def _pct(column: Any, q: float) -> Any:
    return func.percentile_cont(q).within_group(column)


async def collect(session: AsyncSession) -> dict[str, Any]:
    """Aggregates only; nothing here can reveal note content."""
    status_rows = (
        await session.execute(select(Note.status, func.count()).group_by(Note.status))
    ).all()
    by_status = {status: count for status, count in status_rows}
    approved, rejected = by_status.get("APPROVED", 0), by_status.get("REJECTED", 0)
    reviewed = approved + rejected

    edit_ratio = Summary.diff["edit_ratio"].astext.cast(Float)
    edit: Any = (
        await session.execute(
            select(
                func.count(),
                func.avg(edit_ratio),
                func.count().filter(edit_ratio > 0),
            ).where(Summary.diff.is_not(None), Summary.approved_content.is_not(None))
        )
    ).one()
    edited_total, mean_edit, edited_count = edit

    calls: Any = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(LlmCall.outcome != "ok"),
                func.coalesce(func.sum(LlmCall.input_tokens), 0),
                func.coalesce(func.sum(LlmCall.output_tokens), 0),
                func.coalesce(func.sum(LlmCall.cost_usd), 0),
                func.count(func.distinct(LlmCall.note_id)),
                _pct(LlmCall.latency_ms, 0.5).filter(LlmCall.outcome == "ok"),
                _pct(LlmCall.latency_ms, 0.95).filter(LlmCall.outcome == "ok"),
            )
        )
    ).one()
    n_calls, n_failed, tok_in, tok_out, cost, notes_with_calls, lat_p50, lat_p95 = calls

    seconds = cast(func.extract("epoch", Summary.created_at - Note.created_at), Float)
    t2s: Any = (
        await session.execute(
            select(_pct(seconds, 0.5), _pct(seconds, 0.95))
            .select_from(Summary)
            .join(Note, Note.id == Summary.note_id)
            .where(Summary.generation == 1)
        )
    ).one()

    total_cost = Decimal(cost or 0)
    return {
        "notes_total": sum(by_status.values()),
        "notes_by_status": by_status,
        "approval_rate": (approved / reviewed) if reviewed else None,
        "edit_rate": (edited_count / edited_total) if edited_total else None,
        "mean_edit_ratio": float(mean_edit) if mean_edit is not None else None,
        "validation_failure_rate": (n_failed / n_calls) if n_calls else None,
        "llm_calls": n_calls,
        "llm_latency_ms_p50": float(lat_p50) if lat_p50 is not None else None,
        "llm_latency_ms_p95": float(lat_p95) if lat_p95 is not None else None,
        "time_to_summary_s_p50": float(t2s[0]) if t2s[0] is not None else None,
        "time_to_summary_s_p95": float(t2s[1]) if t2s[1] is not None else None,
        "input_tokens": int(tok_in),
        "output_tokens": int(tok_out),
        "cost_usd_total": float(total_cost),
        "cost_usd_per_note": float(total_cost / notes_with_calls) if notes_with_calls else None,
    }
