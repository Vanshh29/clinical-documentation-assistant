"""Liveness heartbeat. The worker writes a timestamp file only while its consumer, outbox relay and
reaper tasks are all alive; the Kubernetes liveness probe runs `python -m cda_worker.health`."""

import asyncio
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path

DEFAULT_PATH = "/tmp/cda-worker-heartbeat"  # noqa: S108 - an emptyDir in the pod
MAX_AGE_SECONDS = 90.0


async def heartbeat(
    path: str, tasks: Sequence["asyncio.Task[object]"], interval: float = 15.0
) -> None:
    while True:
        if all(not t.done() for t in tasks):
            await asyncio.to_thread(Path(path).write_text, str(time.time()))
        await asyncio.sleep(interval)


def is_alive(path: str = DEFAULT_PATH, max_age: float = MAX_AGE_SECONDS) -> bool:
    try:
        return time.time() - os.path.getmtime(path) < max_age
    except OSError:
        return False


if __name__ == "__main__":
    sys.exit(0 if is_alive(os.environ.get("HEARTBEAT_PATH", DEFAULT_PATH)) else 1)
