import contextlib
import os

import pytest
from aiokafka.admin import AIOKafkaAdminClient

from cda_worker.admin_topics import TOPICS, ensure_topics

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")


@pytest.mark.skipif(not BOOTSTRAP, reason="needs a broker: set KAFKA_BOOTSTRAP_SERVERS")
async def test_topics_are_created_with_the_requested_partitions_and_idempotently() -> None:
    assert BOOTSTRAP
    admin = AIOKafkaAdminClient(bootstrap_servers=BOOTSTRAP)
    await admin.start()
    with contextlib.suppress(Exception):  # topics may not exist yet
        await admin.delete_topics(list(TOPICS))
    await admin.close()
    created = await ensure_topics(BOOTSTRAP, partitions=3, replication=1)
    assert set(created) == set(TOPICS)
    assert (
        await ensure_topics(BOOTSTRAP, partitions=3, replication=1) == []
    )  # second run is a no-op
    admin = AIOKafkaAdminClient(bootstrap_servers=BOOTSTRAP)
    await admin.start()
    meta = {t["topic"]: len(t["partitions"]) for t in await admin.describe_topics(list(TOPICS))}
    await admin.close()
    assert meta == {"note.submitted": 3, "summary.ready": 3}
