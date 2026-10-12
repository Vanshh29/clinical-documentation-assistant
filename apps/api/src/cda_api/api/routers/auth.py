from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from cda_api.adapters.db.models import User
from cda_api.adapters.security import TokenService, verify_password
from cda_api.api.deps import PrincipalDep, SessionDep, SettingsDep
from cda_api.api.schemas import LoginRequest, MeResponse, TokenResponse
from cda_api.application import audit
from cda_api.domain.enums import AuditAction, Role
from cda_api.domain.principal import Principal

router = APIRouter(tags=["auth"])

# Verified against when the email is unknown so response time does not reveal valid accounts.
_DUMMY_HASH = "scrypt$" + "00" * 16 + "$" + "00" * 32


@router.post("/auth/token", response_model=TokenResponse)
async def login(body: LoginRequest, session: SessionDep, settings: SettingsDep) -> TokenResponse:
    """Mock OIDC token endpoint for local/demo use (see ADR-002)."""
    user = (
        await session.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    principal = Principal(user_id=user.id, role=Role(user.role), email=user.email)
    token, ttl = TokenService(settings).issue(principal)
    await audit.record(session, AuditAction.LOGIN, "user", user.id, actor=principal)
    return TokenResponse(access_token=token, expires_in=ttl)


@router.get("/me", response_model=MeResponse)
async def me(principal: PrincipalDep, session: SessionDep) -> MeResponse:
    user = (await session.execute(select(User).where(User.id == principal.user_id))).scalar_one()
    return MeResponse(
        id=user.id, email=user.email, role=Role(user.role), display_name=user.display_name
    )
