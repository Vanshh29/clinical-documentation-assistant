import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from cda_api.adapters.db.models import AuditLog
from cda_api.domain.enums import AuditAction
from cda_api.domain.principal import Principal


async def record(
    session: AsyncSession,
    action: AuditAction,
    entity_type: str,
    entity_id: uuid.UUID | None,
    *,
    actor: Principal | None = None,
    request_id: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    schema_version: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Append an audit entry. Callers must pass identifiers and counters only, never note text."""
    session.add(
        AuditLog(
            actor_id=actor.user_id if actor else None,
            actor_role=actor.role.value if actor else None,
            action=action.value,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=request_id or (actor.request_id if actor else None),
            model=model,
            prompt_version=prompt_version,
            schema_version=schema_version,
            details=details or {},
        )
    )
