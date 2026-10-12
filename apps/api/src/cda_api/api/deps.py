from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from cda_api.adapters.db.session import session_scope
from cda_api.adapters.security import TokenService
from cda_api.config import Settings
from cda_api.domain.enums import Role
from cda_api.domain.errors import AuthenticationFailed
from cda_api.domain.principal import Principal


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async for session in session_scope(request.app.state.session_factory):
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def get_principal(
    request: Request,
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        principal = TokenService(settings).verify(authorization[7:])
    except AuthenticationFailed as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return replace(principal, request_id=getattr(request.state, "request_id", None))


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_admin(principal: PrincipalDep) -> Principal:
    if principal.role is not Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin role required")
    return principal


def require_clinician(principal: PrincipalDep) -> Principal:
    if principal.role is not Role.CLINICIAN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "clinician role required")
    return principal


AdminDep = Annotated[Principal, Depends(require_admin)]
ClinicianDep = Annotated[Principal, Depends(require_clinician)]
