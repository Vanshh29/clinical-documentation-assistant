import argparse
import asyncio
import json
import sys
from pathlib import Path

from cda_eval.cases import CASES
from cda_eval.report import render, summary_dict
from cda_eval.runner import (
    VARIANTS,
    build_provider,
    check_thresholds,
    derive_thresholds,
    run_variant,
)

ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS = Path(__file__).resolve().parents[1] / "thresholds.json"
RESULTS = Path(__file__).resolve().parents[1] / "results"


async def main_async(args: argparse.Namespace) -> int:
    provider, model = build_provider(args.provider)
    cases = CASES[: args.limit] if args.limit else CASES
    names = [v.strip() for v in args.variants.split(",") if v.strip()]
    results = {}
    for name in names:
        print(f"running variant {name!r} on {len(cases)} notes ...", flush=True)
        results[name], _ = await run_variant(
            VARIANTS[name], cases, provider, model, concurrency=args.concurrency
        )

    command = f"make eval{'' if args.provider == 'fake' else ' PROVIDER=' + args.provider}"
    report = render(results, provider=args.provider, model=model, command=command, limit=args.limit)
    if not args.no_write:
        out = Path(args.report) if args.report else ROOT / "docs" / "eval-report.md"
        out.write_text(report, encoding="utf-8")
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / f"latest-{args.provider}.json").write_text(
            json.dumps({k: summary_dict(v) for k, v in results.items()}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {out}")

    fixed = results.get("fixed")
    if args.write_thresholds and fixed:
        THRESHOLDS.write_text(
            json.dumps({args.provider: derive_thresholds(fixed)}, indent=2) + "\n"
        )
        print(f"wrote {THRESHOLDS}")
    if args.check:
        if not fixed or args.limit:
            print("--check needs the full dataset and the 'fixed' variant", file=sys.stderr)
            return 2
        thresholds = json.loads(THRESHOLDS.read_text()).get(args.provider)
        if thresholds is None:
            print(f"no thresholds recorded for provider {args.provider!r}", file=sys.stderr)
            return 2
        problems = check_thresholds(fixed, results.get("baseline"), thresholds)
        for p in problems:
            print(f"REGRESSION: {p}", file=sys.stderr)
        print("eval gate:", "FAILED" if problems else "passed")
        return 1 if problems else 0
    return 0


def main() -> None:
    p = argparse.ArgumentParser(prog="cda_eval")
    p.add_argument("--provider", choices=["fake", "openrouter"], default="fake")
    p.add_argument("--variants", default="baseline,fixed")
    p.add_argument(
        "--limit", type=int, default=None, help="only the first N notes (cheap trial run)"
    )
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--check", action="store_true", help="fail if the fixed variant regresses")
    p.add_argument(
        "--write-thresholds", action="store_true", help="record current values as the gate"
    )
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--report", default=None)
    raise SystemExit(asyncio.run(main_async(p.parse_args())))


if __name__ == "__main__":
    main()
