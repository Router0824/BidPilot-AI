from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
import re
from app.domain.models import (
    Requirement, ScoringItem, OutlineSection, DraftVersion,
    RequirementStatus, RiskLevel, ConfirmStatus, ProjectFact, ConfirmationTask,
)
from app.schemas import (
    RequirementUpdate, RequirementMerge, OutlineSectionCreate, OutlineSectionUpdate,
    DraftGenerateRequest,
)


class RequirementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_requirements(self, project_id: str, risk_level: str | None = None,
                                 req_type: str | None = None, status: str | None = None) -> list[Requirement]:
        q = select(Requirement).where(Requirement.project_id == project_id)
        if risk_level:
            q = q.where(Requirement.risk_level == risk_level)
        if req_type:
            q = q.where(Requirement.requirement_type == req_type)
        if status:
            q = q.where(Requirement.status == status)
        q = q.order_by(Requirement.risk_level.desc(), Requirement.created_at)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_requirement(self, req_id: str) -> Requirement | None:
        result = await self.db.execute(select(Requirement).where(Requirement.id == req_id))
        return result.scalar_one_or_none()

    async def update_requirement(self, req_id: str, data: RequirementUpdate) -> Requirement | None:
        req = await self.get_requirement(req_id)
        if not req:
            return None
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(req, k, v)
        await self.db.flush()
        return req

    async def confirm_requirement(self, req_id: str, user: dict) -> Requirement | None:
        req = await self.get_requirement(req_id)
        if not req:
            return None
        req.status = RequirementStatus.CONFIRMED.value
        await self.db.flush()
        return req

    async def merge_requirements(self, data: RequirementMerge) -> dict:
        sources = []
        for sid in data.source_ids:
            r = await self.get_requirement(sid)
            if r:
                sources.append(r)
        if not sources:
            return {"merged": 0}
        target = await self.get_requirement(data.target_id) if data.target_id else sources[0]
        for s in sources:
            if s.id != target.id:
                s.status = RequirementStatus.CONFIRMED.value
                s.response_section_id = target.id
        await self.db.flush()
        return {"merged": len(sources) - 1, "target_id": target.id}

    async def batch_confirm_low_risk(self, project_id: str, user: dict) -> int:
        result = await self.db.execute(
            update(Requirement)
            .where(and_(
                Requirement.project_id == project_id,
                Requirement.risk_level == RiskLevel.LOW.value,
                Requirement.status == RequirementStatus.PENDING.value,
            ))
            .values(status=RequirementStatus.CONFIRMED.value)
        )
        await self.db.flush()
        return result.rowcount


class ScoringService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_scoring_items(self, project_id: str) -> list[ScoringItem]:
        result = await self.db.execute(
            select(ScoringItem).where(ScoringItem.project_id == project_id).order_by(ScoringItem.title)
        )
        return list(result.scalars().all())

    async def get_coverage(self, project_id: str) -> dict:
        result = await self.db.execute(
            select(ScoringItem).where(ScoringItem.project_id == project_id)
        )
        items = result.scalars().all()
        total = len(items)
        covered = sum(1 for i in items if i.coverage_status == "covered")
        total_score = sum(i.score for i in items)
        covered_score = sum(i.score for i in items if i.coverage_status == "covered")
        return {
            "total_items": total,
            "covered_items": covered,
            "coverage_rate": covered / total if total > 0 else 0,
            "total_score": total_score,
            "covered_score": covered_score,
            "score_coverage_rate": covered_score / total_score if total_score > 0 else 0,
        }

    async def merge_cross_page_items(self, project_id: str) -> dict:
        items = await self.list_scoring_items(project_id)
        groups: dict[str, list[ScoringItem]] = {}
        for item in items:
            key = re.sub(r"\s+", "", item.title or "").lower()[:80]
            if not key:
                continue
            groups.setdefault(key, []).append(item)

        merged_count = 0
        manual_required = []
        for grouped in groups.values():
            if len(grouped) < 2:
                continue
            grouped.sort(key=lambda item: (item.source_page or 0, item.created_at))
            base = grouped[0]
            for extra in grouped[1:]:
                adjacent = abs((extra.source_page or 0) - (base.source_page or 0)) <= 1
                if not adjacent:
                    manual_required.append(extra.id)
                    continue
                if extra.criteria and extra.criteria not in (base.criteria or ""):
                    base.criteria = ((base.criteria or "") + "\n" + extra.criteria).strip()
                if extra.evidence and extra.evidence not in (base.evidence or ""):
                    base.evidence = ((base.evidence or "") + "\n" + extra.evidence).strip()
                base.score = max(base.score or 0, extra.score or 0)
                await self.db.delete(extra)
                merged_count += 1
        await self.db.flush()
        return {"merged_items": merged_count, "manual_required_item_ids": manual_required}


class OutlineService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_sections(self, project_id: str) -> list[OutlineSection]:
        result = await self.db.execute(
            select(OutlineSection).where(OutlineSection.project_id == project_id).order_by(OutlineSection.sort_order)
        )
        return list(result.scalars().all())

    async def get_section(self, section_id: str) -> OutlineSection | None:
        result = await self.db.execute(select(OutlineSection).where(OutlineSection.id == section_id))
        return result.scalar_one_or_none()

    async def create_section(self, project_id: str, data: OutlineSectionCreate) -> OutlineSection:
        max_order = (await self.db.execute(
            select(func.max(OutlineSection.sort_order)).where(OutlineSection.project_id == project_id)
        )).scalar() or 0
        section = OutlineSection(
            project_id=project_id,
            parent_id=data.parent_id,
            title=data.title,
            level=data.level,
            sort_order=data.sort_order if data.sort_order > 0 else max_order + 1,
            target_word_count=data.target_word_count,
            owner_id=data.owner_id,
        )
        self.db.add(section)
        await self.db.flush()
        return section

    async def update_section(self, section_id: str, data: OutlineSectionUpdate) -> OutlineSection | None:
        section = await self.get_section(section_id)
        if not section:
            return None
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(section, k, v)
        await self.db.flush()
        return section

    async def delete_section(self, section_id: str) -> bool:
        section = await self.get_section(section_id)
        if not section:
            return False
        await self.db.delete(section)
        await self.db.flush()
        return True

    async def build_tree(self, project_id: str) -> list[dict]:
        sections = await self.list_sections(project_id)
        section_map = {s.id: s for s in sections}
        children_map: dict[str, list] = {}
        roots = []
        for s in sections:
            d = {
                "id": s.id, "project_id": s.project_id, "parent_id": s.parent_id,
                "title": s.title, "level": s.level, "sort_order": s.sort_order,
                "target_word_count": s.target_word_count, "owner_id": s.owner_id,
                "owner_name": s.owner_name, "status": s.status,
                "current_version_id": s.current_version_id,
                "children": [], "created_at": s.created_at, "updated_at": s.updated_at,
            }
            section_map[s.id] = d
            children_map.setdefault(s.parent_id, []).append(d)
            if not s.parent_id:
                roots.append(d)
        for parent_id, children in children_map.items():
            if parent_id and parent_id in section_map:
                section_map[parent_id]["children"] = sorted(children, key=lambda x: x["sort_order"])
        return sorted(roots, key=lambda x: x["sort_order"])


class DraftService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_versions(self, section_id: str) -> list[DraftVersion]:
        result = await self.db.execute(
            select(DraftVersion).where(DraftVersion.section_id == section_id).order_by(DraftVersion.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_version(self, version_id: str) -> DraftVersion | None:
        result = await self.db.execute(select(DraftVersion).where(DraftVersion.id == version_id))
        return result.scalar_one_or_none()

    async def create_draft(self, section_id: str, content: str, citations: list,
                            model_name: str = "mock-llm", prompt_version: str = "1.0.0") -> DraftVersion:
        draft = DraftVersion(
            section_id=section_id,
            content=content,
            citations=citations,
            generated_by="drafting_agent",
            model_name=model_name,
            prompt_version=prompt_version,
            word_count=len(content) if content else 0,
        )
        self.db.add(draft)
        await self.db.flush()

        await self.db.execute(
            update(OutlineSection).where(OutlineSection.id == section_id).values(
                current_version_id=draft.id, status="drafted"
            )
        )
        await self.db.flush()
        return draft
