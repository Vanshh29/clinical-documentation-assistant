"""Write the shared JSON schema consumed by the web app. Run: python -m cda_api.export_schemas"""

import json
import sys
from pathlib import Path

from cda_api.domain.summary_schema import ClinicalSummary

TARGET = (
    Path(__file__).resolve().parents[4] / "packages" / "schemas" / "clinical-summary.schema.json"
)


def render() -> str:
    return json.dumps(ClinicalSummary.model_json_schema(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(0 if TARGET.read_text() == render() else 1)
    TARGET.write_text(render())
    print(f"wrote {TARGET}")
