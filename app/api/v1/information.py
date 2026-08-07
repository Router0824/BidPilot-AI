from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.opportunity_service import OpportunityService
from app.core.auth import require_auth
from app.core.database import get_db
from app.schemas import APIResponse


router = APIRouter(prefix="/information", tags=["information"])


class MonitorRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_url: str | None = None
    keywords: list[str] | str = []
    regions: list[str] | str = []
    industry: str | None = None
    interval_minutes: int = 1440
    enabled: bool = True


@router.get("/monitors")
async def list_monitors(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = OpportunityService(db)
    return APIResponse(data=[svc.monitor_dict(monitor) for monitor in await svc.list_monitors()])


@router.post("/monitors")
async def create_monitor(
    data: MonitorRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = OpportunityService(db)
    monitor = await svc.create_monitor(data.model_dump(), user)
    return APIResponse(data=svc.monitor_dict(monitor))


@router.post("/monitors/{monitor_id}/run")
async def run_monitor(
    monitor_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = OpportunityService(db)
    try:
        return APIResponse(data=await svc.run_monitor(monitor_id))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/opportunities/refresh-all")
async def refresh_all(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    return APIResponse(data=await OpportunityService(db).refresh_all())


@router.get("/opportunities")
async def list_opportunities(
    monitor_id: str | None = Query(None),
    limit: int = Query(80, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = OpportunityService(db)
    opportunities = await svc.list_opportunities(monitor_id, limit)
    return APIResponse(data=[svc.opportunity_dict(opp) for opp in opportunities])
