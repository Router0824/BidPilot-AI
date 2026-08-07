from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import MOCK_USERS
from app.domain.models import (
    AuditLog,
    ConfirmationTask,
    DraftVersion,
    OutlineSection,
    ProjectMember,
    SectionApproval,
    SectionLock,
)


INDUSTRY_TEMPLATES = {
    "software": [
        ("项目概述与理解", 1), ("项目背景", 2), ("需求理解", 2),
        ("总体技术方案", 1), ("系统总体架构", 2), ("技术架构设计", 2), ("数据架构设计", 2), ("安全方案", 2),
        ("项目实施", 1), ("实施计划", 2), ("项目组织与人员", 2), ("质量保证", 2),
        ("培训与售后服务", 1), ("培训方案", 2), ("售后服务与技术支持", 2),
        ("公司资质与案例", 1), ("公司资质", 2), ("同类案例", 2),
    ],
    "construction": [
        ("工程概况", 1), ("施工组织总体部署", 1), ("施工进度计划", 2), ("资源配置计划", 2),
        ("主要施工方案", 1), ("质量管理体系", 1), ("安全文明施工", 1), ("绿色施工措施", 2),
        ("项目管理机构", 1), ("类似工程业绩", 1),
    ],
    "medical": [
        ("项目理解", 1), ("医疗业务需求响应", 1), ("系统功能方案", 1), ("数据安全与隐私保护", 1),
        ("实施与培训", 1), ("售后服务", 1), ("资质与合规证明", 1), ("成功案例", 1),
    ],
    "education": [
        ("项目背景与目标", 1), ("教学业务理解", 1), ("平台建设方案", 1), ("数据治理方案", 2),
        ("实施推广计划", 1), ("培训与运维", 1), ("安全与合规", 1), ("案例与资质", 1),
    ],
}


def user_display_name(user_id: str) -> str:
    for user in MOCK_USERS.values():
        if user["id"] == user_id:
            return user["display_name"]
    return user_id


class EnterpriseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def audit(
        self,
        resource_type: str,
        resource_id: str,
        action: str,
        user: dict | None,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
    ) -> AuditLog:
        item = AuditLog(
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            operator=(user or {}).get("id", "system"),
            before_value=before,
            after_value=after,
            reason=reason,
        )
        self.db.add(item)
        await self.db.flush()
        return item

    async def list_audits(self, project_id: str | None = None, limit: int = 100) -> list[AuditLog]:
        query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if project_id:
            query = query.where(AuditLog.resource_id == project_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_members(self, project_id: str) -> list[ProjectMember]:
        result = await self.db.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id).order_by(ProjectMember.created_at)
        )
        return list(result.scalars().all())

    async def upsert_member(self, project_id: str, user_id: str, role: str, operator: dict) -> ProjectMember:
        member = (await self.db.execute(
            select(ProjectMember).where(and_(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id))
        )).scalar_one_or_none()
        before = {"role": member.role} if member else None
        if not member:
            member = ProjectMember(project_id=project_id, user_id=user_id, user_name=user_display_name(user_id))
            self.db.add(member)
        member.role = role
        member.access_level = "admin" if role in ("project_admin", "reviewer") else "write"
        await self.audit("project_member", project_id, "member_upsert", operator, before, {"user_id": user_id, "role": role})
        await self.db.flush()
        return member

    async def assign_section(self, section_id: str, user_id: str, operator: dict) -> OutlineSection | None:
        section = (await self.db.execute(select(OutlineSection).where(OutlineSection.id == section_id))).scalar_one_or_none()
        if not section:
            return None
        before = {"owner_id": section.owner_id, "owner_name": section.owner_name}
        section.owner_id = user_id
        section.owner_name = user_display_name(user_id)
        task = ConfirmationTask(
            project_id=section.project_id,
            task_type="section_assignment",
            resource_type="outline_section",
            resource_id=section.id,
            candidate_value={"section_title": section.title, "assigned_to": user_id, "assigned_to_name": section.owner_name},
            assigned_to=user_id,
            risk_level="low",
            created_node="manual_assignment",
        )
        self.db.add(task)
        await self.audit("outline_section", section.project_id, "assign_section", operator, before, {"owner_id": user_id})
        await self.db.flush()
        return section

    async def can_edit_section(self, section: OutlineSection, user: dict) -> bool:
        if user["role"] in ("admin", "project_admin"):
            return True
        if not section.owner_id:
            return user["role"] in ("writer", "reviewer")
        return section.owner_id == user["id"]

    async def acquire_lock(self, section_id: str, user: dict, client_id: str | None = None) -> dict:
        section = (await self.db.execute(select(OutlineSection).where(OutlineSection.id == section_id))).scalar_one_or_none()
        if not section:
            return {"error": "section_not_found"}
        if not await self.can_edit_section(section, user):
            return {"error": "permission_denied"}
        now = datetime.now(timezone.utc)
        existing = (await self.db.execute(
            select(SectionLock).where(SectionLock.section_id == section_id, SectionLock.expires_at > now)
        )).scalar_one_or_none()
        if existing and existing.locked_by != user["id"]:
            return {"error": "locked", "locked_by": existing.locked_by_name}
        if not existing:
            existing = SectionLock(section_id=section.id, project_id=section.project_id, locked_by=user["id"])
            self.db.add(existing)
        existing.locked_by_name = user.get("display_name", user["username"])
        existing.client_id = client_id
        existing.expires_at = now + timedelta(minutes=5)
        await self.db.flush()
        return {"lock_id": existing.id, "section_id": section_id, "expires_at": existing.expires_at}

    async def release_lock(self, section_id: str, user: dict) -> bool:
        result = await self.db.execute(
            select(SectionLock).where(SectionLock.section_id == section_id, SectionLock.locked_by == user["id"])
        )
        locks = result.scalars().all()
        for lock in locks:
            await self.db.delete(lock)
        await self.db.flush()
        return bool(locks)

    async def submit_section_approval(self, section_id: str, reviewer_id: str | None, user: dict) -> SectionApproval | None:
        section = (await self.db.execute(select(OutlineSection).where(OutlineSection.id == section_id))).scalar_one_or_none()
        if not section:
            return None
        draft_id = section.current_version_id
        approval = SectionApproval(
            section_id=section.id,
            project_id=section.project_id,
            draft_version_id=draft_id,
            submitted_by=user["id"],
            reviewer_id=reviewer_id,
            reviewer_name=user_display_name(reviewer_id) if reviewer_id else None,
            status="pending",
        )
        self.db.add(approval)
        section.status = "review_pending"
        await self.audit("outline_section", section.project_id, "submit_approval", user, None, {"section_id": section.id, "reviewer_id": reviewer_id})
        await self.db.flush()
        return approval

    async def resolve_approval(self, approval_id: str, action: str, comment: str | None, user: dict) -> SectionApproval | None:
        approval = (await self.db.execute(select(SectionApproval).where(SectionApproval.id == approval_id))).scalar_one_or_none()
        if not approval:
            return None
        approval.status = "approved" if action == "approve" else "rejected"
        approval.comment = comment
        approval.resolved_at = datetime.now(timezone.utc)
        section = (await self.db.execute(select(OutlineSection).where(OutlineSection.id == approval.section_id))).scalar_one_or_none()
        if section:
            section.status = "approved" if action == "approve" else "rejected"
        await self.audit("section_approval", approval.project_id, f"approval_{action}", user, None, {"approval_id": approval.id, "comment": comment})
        await self.db.flush()
        return approval

    async def list_approvals(self, project_id: str) -> list[SectionApproval]:
        result = await self.db.execute(
            select(SectionApproval).where(SectionApproval.project_id == project_id).order_by(SectionApproval.created_at.desc())
        )
        return list(result.scalars().all())

    async def apply_template(self, project_id: str, template_key: str, user: dict) -> dict:
        template = INDUSTRY_TEMPLATES.get(template_key)
        if not template:
            return {"error": "template_not_found"}
        existing_count = (await self.db.execute(
            select(OutlineSection).where(OutlineSection.project_id == project_id)
        )).scalars().all()
        base_order = len(existing_count)
        created = []
        for idx, (title, level) in enumerate(template, start=1):
            section = OutlineSection(
                project_id=project_id,
                title=title,
                level=level,
                sort_order=base_order + idx,
                status="pending",
            )
            self.db.add(section)
            created.append(section)
        await self.audit("outline_template", project_id, "apply_template", user, None, {"template_key": template_key, "sections": len(created)})
        await self.db.flush()
        return {"template_key": template_key, "created_sections": len(created)}

    async def list_templates(self) -> list[dict]:
        return [{"key": key, "name": self.template_name(key), "section_count": len(items)} for key, items in INDUSTRY_TEMPLATES.items()]

    def template_name(self, key: str) -> str:
        return {
            "software": "软件信息化",
            "construction": "建筑工程",
            "medical": "医疗卫生",
            "education": "教育行业",
        }.get(key, key)
