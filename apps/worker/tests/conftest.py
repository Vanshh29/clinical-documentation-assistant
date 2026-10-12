import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from cda_api.adapters.crypto import MappingCipher
from cda_api.adapters.db.session import make_engine, make_session_factory
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cda_worker.adapters.redactor import PresidioRedactor

API_ROOT = Path(__file__).resolve().parents[2] / "api"


@pytest.fixture(scope="session")
def redactor() -> PresidioRedactor:
    return PresidioRedactor()


@pytest.fixture(scope="session")
def cipher() -> MappingCipher:
    return MappingCipher(Fernet.generate_key().decode())


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    url = os.environ.get("TEST_DATABASE_URL")
    container = None
    if not url:
        os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
        from testcontainers.postgres import PostgresContainer

        container = PostgresContainer("postgres:16.4-alpine", driver="asyncpg")
        container.start()
        url = container.get_connection_url()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        env={**os.environ, "DATABASE_URL": url, "PYTHONPATH": str(API_ROOT / "src")},
        check=True,
    )
    yield url
    if container:
        container.stop()


@pytest_asyncio.fixture(scope="session")
async def session_factory(database_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = make_engine(database_url)
    yield make_session_factory(engine)
    await engine.dispose()
