from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.domain.models import Project, Requirement, ConfirmationTask, Document, RiskLevel, RequirementStatus, ConfirmStatus
from app.schemas import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_projects(self, status: str | None = None, owner_id: str | None = None) -> list[dict]:
        q = select(Project)
        if status:
            q = q.where(Project.status == status)
        if owner_id:
            q = q.where(Project.owner_id == owner_id)
        q = q.order_by(Project.updated_at.desc())
        result = await self.db.execute(q)
        projects = result.scalars().all()

        resp = []
        for p in projects:
            doc_count = (await self.db.execute(
                select(func.count(Document.id)).where(Document.project_id == p.id)
            )).scalar() or 0
            req_count = (await self.db.execute(
                select(func.count(Requirement.id)).where(Requirement.project_id == p.id)
            )).scalar() or 0
            high_risk = (await self.db.execute(
                select(func.count(Requirement.id)).where(
                    and_(Requirement.project_id == p.id, Requirement.risk_level == RiskLevel.HIGH.value)
                )
            )).scalar() or 0
            pending = (await self.db.execute(
                select(func.count(ConfirmationTask.id)).where(
                    and_(ConfirmationTask.project_id == p.id, ConfirmationTask.status == "pending")
                )
            )).scalar() or 0
            resp.append({
                "id": p.id, "name": p.name, "project_type": p.project_type,
                "owner_id": p.owner_id, "owner_name": p.owner_name,
                "deadline": p.deadline, "status": p.status,
                "workflow_status": p.workflow_status, "description": p.description,
                "document_count": doc_count,
                "requirement_count": req_count, "high_risk_count": high_risk,
                "pending_confirmation_count": pending, "outline_completion": 0.0,
                "created_at": p.created_at, "updated_at": p.updated_at,
            })
        return resp

    async def get_project(self, project_id: str) -> Project | None:
        result = await self.db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def create_project(self, data: ProjectCreate, user: dict) -> Project:
        project = Project(
            name=data.name,
            project_type=data.project_type,
            description=data.description,
            deadline=data.deadline,
            owner_id=data.owner_id or user["id"],
            owner_name=user.get("display_name", user["username"]),
        )
        self.db.add(project)
        await self.db.flush()
        return project

    async def update_project(self, project_id: str, data: ProjectUpdate) -> Project | None:
        project = await self.get_project(project_id)
        if not project:
            return None
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(project, k, v)
        await self.db.flush()
        return project

    async def delete_project(self, project_id: str) -> bool:
        project = await self.get_project(project_id)
        if not project:
            return False
        await self.db.delete(project)
        await self.db.flush()
        return True