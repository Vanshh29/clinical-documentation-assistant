from fastapi import APIRouter, Query
from sqlalchemy import func, select

from cda_api.adapters.db.models import AuditLog
from cda_api.api.deps import AdminDep, SessionDep
from cda_api.api.schemas import AuditEntry, AuditPage, MetricsOut
from cda_api.application import metrics as metrics_svc

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit", response_model=AuditPage)
async def list_audit(
    _admin: AdminDep,
    session: SessionDep,
    action: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditPage:
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (
        await session.execute(query.order_by(AuditLog.id.desc()).limit(limit).offset(offset))
    ).scalars()
    return AuditPage(items=[AuditEntry.model_validate(r) for r in rows], total=total)


@router.get("/metrics", response_model=MetricsOut)
async def get_metrics(_admin: AdminDep, session: SessionDep) -> MetricsOut:
    return MetricsOut(**await metrics_svc.collect(session))
