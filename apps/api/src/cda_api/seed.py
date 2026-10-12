"""Create demo users (local/demo only). Run: python -m cda_api.seed"""

import asyncio
import os

from sqlalchemy import select

from cda_api.adapters.db.models import User
from cda_api.adapters.db.session import make_engine, make_session_factory
from cda_api.adapters.security import hash_password
from cda_api.config import get_settings

DEMO_USERS = [
    ("clinician1@demo.example", "Dr. Demo Clinician One", "clinician"),
    ("clinician2@demo.example", "Dr. Demo Clinician Two", "clinician"),
    ("admin@demo.example", "Demo Admin", "admin"),
]


async def seed() -> None:
    password = os.environ.get("SEED_PASSWORD", "demo-password-123")
    engine = make_engine(get_settings().database_url)
    factory = make_session_factory(engine)
    async with factory() as session:
        for email, name, role in DEMO_USERS:
            exists = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    User(
                        email=email,
                        display_name=name,
                        role=role,
                        password_hash=hash_password(password),
                    )
                )
        await session.commit()
    await engine.dispose()
    print(f"Seeded {len(DEMO_USERS)} demo users (password from SEED_PASSWORD or default).")


if __name__ == "__main__":
    asyncio.run(seed())
