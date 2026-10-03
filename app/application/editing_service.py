from fastapi import HTTPException
from sqlalchemy import select, update, exists

from app.domain.models import OutlineSection, DraftVersion, SectionProtection, Requirement
from app.application.enterprise_service import EnterpriseService


async def write_version(db, section, content, citations, expected_version_id,
                        actor="drafting_agent", model="manual", protect=False):
    """Compare-and-swap prevents a slow generation from replacing a newer edit."""
    draft = DraftVersion(section_id=section.id, content=content, citations=citations,
                         generated_by=actor, model_name=model, word_count=len(content))
    db.add(draft)
    await db.flush()
    condition = [OutlineSection.id == section.id,
                 OutlineSection.current_version_id == expected_version_id]
    if actor in ("drafting_agent", "fixer_agent"):
        condition.append(~exists().where(
            SectionProtection.section_id == section.id,
            SectionProtection.protected.is_(True)))
    result = await db.execute(update(OutlineSection).where(*condition).values(
        current_version_id=draft.id, status="drafted"))
    if not result.rowcount:
        await db.delete(draft)
        await db.flush()
        raise HTTPException(409, "章节已更新或受到保护，请刷新后再操作；您的编辑未被覆盖")
    if protect:
        await set_protection(db, section.id, True, actor)
    await db.execute(update(Requirement).where(Requirement.project_id == section.project_id,
        Requirement.response_section_id == section.id, Requirement.status == "responded").values(status="confirmed"))
    await db.flush()
    return draft


async def set_protection(db, section_id, protected, actor):
    state = await db.get(SectionProtection, section_id)
    if state is None:
        state = SectionProtection(section_id=section_id)
        db.add(state)
    state.protected = protected
    state.updated_by = actor
    await db.flush()


async def editable_section(db, project_id, section_id, user):
    section = await db.get(OutlineSection, section_id)
    if not section or section.project_id != project_id:
        raise HTTPException(404, "章节不存在")
    if not await EnterpriseService(db).can_edit_section(section, user):
        raise HTTPException(403, "仅章节负责人或项目管理员可编辑")
    return section
