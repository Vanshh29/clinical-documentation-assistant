import asyncio
import os
import time
from pathlib import Path

from cda_worker.health import heartbeat, is_alive


def test_stale_or_missing_heartbeat_is_not_alive(tmp_path: Path) -> None:
    f = tmp_path / "hb"
    assert not is_alive(str(f))
    f.write_text("x")
    assert is_alive(str(f), max_age=30)
    old = time.time() - 300
    os.utime(f, (old, old))
    assert not is_alive(str(f), max_age=90)


async def test_heartbeat_stops_when_a_worker_task_dies(tmp_path: Path) -> None:
    path = tmp_path / "hb"

    async def forever() -> None:
        await asyncio.sleep(3600)

    async def crashes() -> None:
        raise RuntimeError("consumer died")

    healthy = asyncio.create_task(forever())
    beat = asyncio.create_task(heartbeat(str(path), [healthy], interval=0.01))
    await asyncio.sleep(0.05)
    assert path.exists()
    beat.cancel()
    path.unlink()

    dead = asyncio.create_task(crashes())
    await asyncio.sleep(0.01)
    beat = asyncio.create_task(heartbeat(str(path), [healthy, dead], interval=0.01))
    await asyncio.sleep(0.05)
    assert not path.exists()  # a dead task means no heartbeat, so the probe restarts the pod
    for t in (beat, healthy):
        t.cancel()
