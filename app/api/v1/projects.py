from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import require_auth
from app.application.project_service import ProjectService
from app.application.enterprise_service import EnterpriseService
from app.domain.models import Project, Requirement, ConfirmationTask, Document, RiskLevel
from app.schemas import ProjectCreate, ProjectUpdate, ProjectResponse, APIResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects(
    status: str | None = Query(None),
    owner_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = ProjectService(db)
    projects = await svc.list_projects(status=status, owner_id=owner_id)
    return APIResponse(data=projects)


@router.post("")
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = ProjectService(db)
    project = await svc.create_project(data, user)
    await EnterpriseService(db).audit("project", project.id, "create", user, None, {"name": project.name})
    return APIResponse(data={
        "id": project.id, "name": project.name, "project_type": project.project_type,
        "workflow_status": project.workflow_status, "created_at": str(project.created_at),
    })


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = ProjectService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    # Use count queries instead of lazy-loaded relationships
    doc_count = (await db.execute(
        select(func.count(Document.id)).where(Document.project_id == project_id)
    )).scalar() or 0
    req_count = (await db.execute(
        select(func.count(Requirement.id)).where(Requirement.project_id == project_id)
    )).scalar() or 0
    high_risk = (await db.execute(
        select(func.count(Requirement.id)).where(
            and_(Requirement.project_id == project_id, Requirement.risk_level == RiskLevel.HIGH.value)
        )
    )).scalar() or 0
    pending = (await db.execute(
        select(func.count(ConfirmationTask.id)).where(
            and_(ConfirmationTask.project_id == project_id, ConfirmationTask.status == "pending")
        )
    )).scalar() or 0
    return APIResponse(data={
        "id": project.id, "name": project.name, "project_type": project.project_type,
        "owner_id": project.owner_id, "owner_name": project.owner_name,
        "deadline": str(project.deadline) if project.deadline else None,
        "status": project.status, "workflow_status": project.workflow_status,
        "description": project.description,
        "document_count": doc_count,
        "requirement_count": req_count,
        "high_risk_count": high_risk,
        "pending_confirmation_count": pending,
        "outline_completion": 0.0,
        "created_at": str(project.created_at), "updated_at": str(project.updated_at),
    })


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = ProjectService(db)
    project = await svc.update_project(project_id, data)
    if not project:
        raise HTTPException(404, "项目不存在")
    await EnterpriseService(db).audit("project", project_id, "update", user, None, data.model_dump(exclude_unset=True))
    return APIResponse(data={"id": project.id, "status": "updated"})


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = ProjectService(db)
    ok = await svc.delete_project(project_id)
    if not ok:
        raise HTTPException(404, "项目不存在")
    await EnterpriseService(db).audit("project", project_id, "delete", user)
    return APIResponse(data={"deleted": True})
