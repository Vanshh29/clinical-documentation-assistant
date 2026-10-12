import uuid
from dataclasses import dataclass

from cda_api.domain.enums import Role


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    role: Role
    email: str
    request_id: str | None = None
