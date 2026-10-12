"""Create the Kafka topics with the configured partition count (idempotent).

Brokers auto-create topics with one partition, which caps the worker at one consumer. Run once per
release (the Helm chart does this in a hook job): `python -m cda_worker.admin_topics`.
"""

import asyncio
import logging
import os

from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError

log = logging.getLogger("cda.worker.topics")

TOPICS = ("note.submitted", "summary.ready")


async def ensure_topics(bootstrap: str, partitions: int, replication: int) -> list[str]:
    admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap)
    await admin.start()
    created: list[str] = []
    try:
        existing = set(await admin.list_topics())
        for name in TOPICS:
            if name in existing:
                continue
            try:
                await admin.create_topics(
                    [NewTopic(name, num_partitions=partitions, replication_factor=replication)]
                )
                created.append(name)
            except TopicAlreadyExistsError:  # raced with another replica
                continue
    finally:
        await admin.close()
    return created


def main() -> None:
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    partitions = int(os.environ.get("KAFKA_TOPIC_PARTITIONS", "3"))
    replication = int(os.environ.get("KAFKA_REPLICATION_FACTOR", "1"))
    created = asyncio.run(ensure_topics(bootstrap, partitions, replication))
    print(f"topics ready (created: {created or 'none, already present'})")


if __name__ == "__main__":
    main()
