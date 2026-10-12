"""Submit notes concurrently and measure how long each takes to reach review.

    apps/api/.venv/bin/python scripts/load_test.py --notes 100 --concurrency 10

Uses the demo clinician account against a running stack (`make up`). It measures the whole path: HTTP
submit, outbox relay, Kafka, redaction, the model provider and validation. With the default offline provider
it therefore measures the pipeline, not a language model.
"""

import argparse
import asyncio
import json
import statistics
import time

import httpx

SAMPLES = [
    (
        "Patientin Anna Beispiel (geb. 03.04.1961) klagt seit drei Tagen über Husten und Fieber bis 38,9 Grad. "
        "Sie nimmt Ramipril 5 mg morgens. Keine bekannten Allergien. Beurteilung: Verdacht auf Bronchitis. "
        "Plan: Hustensaft und Ruhe. Kontrolle in 2 Wochen."
    ),
    (
        "Jordan Example (DOB: 14 March 1975) presents with cough for three days and a sore throat. Takes "
        "lisinopril 10 mg once daily. Allergic to penicillin. Assessment: viral upper respiratory infection "
        "suspected. Plan: rest, fluids and paracetamol 500 mg as needed. Follow-up in two weeks."
    ),
    (
        "pt c/o SOB x3d, worse w/ exertion. hx HTN, T2DM. meds: lisinopril 10mg qd, metformin 500 bid. NKDA.\n"
        "A: likely URI, r/o pneumonia\nP: CXR, rest, fluids\nf/u 1wk"
    ),
]


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


async def one(
    client: httpx.AsyncClient, i: int, timeout: float
) -> dict[str, float | str]:
    body = SAMPLES[i % len(SAMPLES)] + f" (load test note {i})"
    started = time.perf_counter()
    r = await client.post(
        "/notes", json={"body": body, "title": f"load {i}", "language": "auto"}
    )
    submit_s = time.perf_counter() - started
    if r.status_code != 201:
        return {
            "id": "",
            "status": f"submit_{r.status_code}",
            "submit_s": submit_s,
            "ready_s": float("nan"),
        }
    note_id = r.json()["id"]
    while time.perf_counter() - started < timeout:
        s = (await client.get(f"/notes/{note_id}")).json()["status"]
        if s in ("PENDING_REVIEW", "FAILED_VALIDATION"):
            return {
                "id": note_id,
                "status": s,
                "submit_s": submit_s,
                "ready_s": time.perf_counter() - started,
            }
        await asyncio.sleep(0.1)
    return {
        "id": note_id,
        "status": "TIMEOUT",
        "submit_s": submit_s,
        "ready_s": float("nan"),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8080/api")
    ap.add_argument("--email", default="clinician1@demo.example")
    ap.add_argument("--password", default="demo-password-123")
    ap.add_argument("--notes", type=int, default=100)
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--timeout", type=float, default=120)
    args = ap.parse_args()

    async with httpx.AsyncClient(base_url=args.base, timeout=30) as login:
        token = (
            await login.post(
                "/auth/token", json={"email": args.email, "password": args.password}
            )
        ).json()["access_token"]
    limits = httpx.Limits(max_connections=args.concurrency * 2)
    async with httpx.AsyncClient(
        base_url=args.base,
        timeout=30,
        limits=limits,
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        gate = asyncio.Semaphore(args.concurrency)

        async def guarded(i: int) -> dict[str, float | str]:
            async with gate:
                return await one(client, i, args.timeout)

        t0 = time.perf_counter()
        rows = await asyncio.gather(*(guarded(i) for i in range(args.notes)))
        wall = time.perf_counter() - t0

    ok = [r for r in rows if r["status"] == "PENDING_REVIEW"]
    ready = [float(r["ready_s"]) for r in ok]
    submit = [float(r["submit_s"]) for r in rows]
    result = {
        "notes": args.notes,
        "concurrency": args.concurrency,
        "reached_review": len(ok),
        "not_ok": {
            s: sum(r["status"] == s for r in rows)
            for s in {str(r["status"]) for r in rows} - {"PENDING_REVIEW"}
        },
        "wall_seconds": round(wall, 2),
        "throughput_notes_per_second": round(len(ok) / wall, 2),
        "submit_ms_p50": round(pct(submit, 0.5) * 1000, 1),
        "submit_ms_p95": round(pct(submit, 0.95) * 1000, 1),
        "time_to_review_s_p50": round(pct(ready, 0.5), 2) if ready else None,
        "time_to_review_s_p95": round(pct(ready, 0.95), 2) if ready else None,
        "time_to_review_s_max": round(max(ready), 2) if ready else None,
        "time_to_review_s_mean": round(statistics.mean(ready), 2) if ready else None,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
