import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cda_api.adapters.db.models import User
from cda_api.adapters.security import TokenService, hash_password
from cda_api.config import Settings
from cda_api.domain.enums import Role
from cda_api.domain.principal import Principal
from cda_api.main import create_app

API_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "test-password-123"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Real Postgres: TEST_DATABASE_URL if set (CI service), else a Testcontainers instance."""
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
        env={**os.environ, "DATABASE_URL": url},
        check=True,
    )
    yield url
    if container:
        container.stop()


@pytest_asyncio.fixture(scope="session")
async def app(database_url: str) -> AsyncIterator[FastAPI]:
    application = create_app(
        Settings(database_url=database_url, log_level="WARNING", metrics_port=0)
    )
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def session_factory(app: FastAPI) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = app.state.session_factory
    return factory


class Account:
    def __init__(self, user_id: uuid.UUID, role: Role, email: str, token: str) -> None:
        self.id = user_id
        self.role = role
        self.email = email
        self.headers = {"Authorization": f"Bearer {token}"}
        self.principal = Principal(user_id=user_id, role=role, email=email)


@pytest_asyncio.fixture
async def make_account(app: FastAPI, session_factory: async_sessionmaker[AsyncSession]):  # type: ignore[no-untyped-def]
    async def _make(role: Role = Role.CLINICIAN) -> Account:
        email = f"{role.value}-{uuid.uuid4().hex[:8]}@test.example"
        async with session_factory() as s:
            user = User(
                email=email,
                display_name="Test User",
                role=role.value,
                password_hash=hash_password(PASSWORD),
            )
            s.add(user)
            await s.commit()
            principal = Principal(user_id=user.id, role=role, email=email)
        token, _ = TokenService(app.state.settings).issue(principal)
        return Account(principal.user_id, role, email, token)

    return _make
