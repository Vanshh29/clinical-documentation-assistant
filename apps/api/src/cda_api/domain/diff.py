"""Diff between the model output and the clinician-approved summary."""

import difflib
import json
from typing import Any

from cda_api.domain.summary_schema import FIELD_NAMES


def _render(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def summary_diff(model_output: dict[str, Any], approved: dict[str, Any]) -> dict[str, Any]:
    """Field-level diff plus an edit ratio in [0, 1] (0 = unchanged, 1 = fully rewritten).

    Only field values are compared; confidence and spans are metadata.
    """
    changes: dict[str, dict[str, Any]] = {}
    ratios: list[float] = []
    for name in FIELD_NAMES:
        before = model_output.get(name, {}).get("value")
        after = approved.get(name, {}).get("value")
        if before == after:
            ratios.append(0.0)
            continue
        changes[name] = {"before": before, "after": after}
        similarity = difflib.SequenceMatcher(None, _render(before), _render(after)).ratio()
        ratios.append(1.0 - similarity)
    edit_ratio = sum(ratios) / len(FIELD_NAMES)
    return {"changed_fields": changes, "edit_ratio": round(edit_ratio, 4)}
