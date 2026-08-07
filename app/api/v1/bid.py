from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import require_auth
from app.application.bid_services import RequirementService, ScoringService, OutlineService, DraftService
from app.application.confidence_service import ConfidenceService
from app.application.enterprise_service import EnterpriseService
from app.application.review_export_service import ReviewService, ExportService
from app.schemas import (
    APIResponse, RequirementUpdate, RequirementMerge,
    OutlineSectionCreate, OutlineSectionUpdate, DraftGenerateRequest,
    ExportRequest, ConfirmationAction,
)
from app.workflows.workflow_service import WorkflowService
from app.domain.models import ConfirmationTask, ProjectFact, ConfirmStatus
from app.observability.progress import progress_context, publish_progress

router = APIRouter(prefix="/projects/{project_id}", tags=["bid"])


# ── Requirements ──
@router.get("/requirements")
async def list_requirements(
    project_id: str,
    risk_level: str | None = Query(None),
    req_type: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = RequirementService(db)
    reqs = await svc.list_requirements(project_id, risk_level, req_type, status)
    confidence = ConfidenceService(db)
    payload = []
    for r in reqs:
        detail = await confidence.requirement_confidence(r)
        payload.append({
            "id": r.id, "project_id": r.project_id, "requirement_text": r.requirement_text,
            "requirement_type": r.requirement_type, "mandatory": r.mandatory,
            "risk_level": r.risk_level, "evidence_required": r.evidence_required,
            "source_document_id": r.source_document_id, "source_page": r.source_page,
            "confidence": detail.score, "confidence_detail": detail.as_dict(),
            "response_section_id": r.response_section_id,
            "owner_id": r.owner_id, "owner_name": r.owner_name, "status": r.status,
            "review_status": r.review_status, "subject": r.subject,
            "action": r.action, "condition": r.condition, "deadline": r.deadline,
            "created_at": str(r.created_at), "updated_at": str(r.updated_at),
        })
    return APIResponse(data=payload)


@router.patch("/requirements/{requirement_id}")
async def update_requirement(
    project_id: str, requirement_id: str, data: RequirementUpdate,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = RequirementService(db)
    req = await svc.update_requirement(requirement_id, data)
    if not req:
        raise HTTPException(404, "要求不存在")
    return APIResponse(data={"id": req.id, "status": "updated"})


@router.post("/requirements/{requirement_id}/confirm")
async def confirm_requirement(
    project_id: str, requirement_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = RequirementService(db)
    req = await svc.confirm_requirement(requirement_id, user)
    if not req:
        raise HTTPException(404, "要求不存在")
    await EnterpriseService(db).audit("requirement", project_id, "confirm", user, None, {"requirement_id": req.id})
    return APIResponse(data={"id": req.id, "status": req.status})


@router.post("/requirements/merge")
async def merge_requirements(
    project_id: str, data: RequirementMerge,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = RequirementService(db)
    result = await svc.merge_requirements(data)
    return APIResponse(data=result)


@router.post("/requirements/batch-confirm")
async def batch_confirm(
    project_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = RequirementService(db)
    count = await svc.batch_confirm_low_risk(project_id, user)
    return APIResponse(data={"confirmed_count": count})


# ── Scoring ──
@router.get("/scoring")
async def list_scoring(
    project_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = ScoringService(db)
    items = await svc.list_scoring_items(project_id)
    return APIResponse(data=[{
        "id": s.id, "project_id": s.project_id, "parent_id": s.parent_id,
        "title": s.title, "score": s.score, "min_score": s.min_score,
        "max_score": s.max_score, "criteria": s.criteria, "evidence": s.evidence,
        "source_document_id": s.source_document_id, "source_page": s.source_page,
        "coverage_status": s.coverage_status, "suggested_section_id": s.suggested_section_id,
    } for s in items])


@router.get("/scoring/coverage")
async def scoring_coverage(
    project_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = ScoringService(db)
    coverage = await svc.get_coverage(project_id)
    return APIResponse(data=coverage)


@router.post("/scoring/merge-cross-page")
async def merge_cross_page_scoring(
    project_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = ScoringService(db)
    return APIResponse(data=await svc.merge_cross_page_items(project_id))


# ── Outline ──
@router.get("/outline")
async def get_outline(
    project_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = OutlineService(db)
    tree = await svc.build_tree(project_id)
    return APIResponse(data=tree)


@router.post("/outline/sections")
async def create_section(
    project_id: str, data: OutlineSectionCreate,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = OutlineService(db)
    section = await svc.create_section(project_id, data)
    return APIResponse(data={"id": section.id, "title": section.title, "level": section.level})


@router.patch("/outline/sections/{section_id}")
async def update_section(
    project_id: str, section_id: str, data: OutlineSectionUpdate,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = OutlineService(db)
    enterprise = EnterpriseService(db)
    existing = await svc.get_section(section_id)
    if existing and not await enterprise.can_edit_section(existing, user):
        raise HTTPException(403, "仅章节负责人或项目管理员可编辑")
    section = await svc.update_section(section_id, data)
    if not section:
        raise HTTPException(404, "章节不存在")
    await enterprise.audit("outline_section", project_id, "update", user, None, data.model_dump(exclude_unset=True))
    return APIResponse(data={"id": section.id, "status": "updated"})


@router.delete("/outline/sections/{section_id}")
async def delete_section(
    project_id: str, section_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = OutlineService(db)
    enterprise = EnterpriseService(db)
    existing = await svc.get_section(section_id)
    if existing and not await enterprise.can_edit_section(existing, user):
        raise HTTPException(403, "仅章节负责人或项目管理员可删除")
    ok = await svc.delete_section(section_id)
    if not ok:
        raise HTTPException(404, "章节不存在")
    await enterprise.audit("outline_section", project_id, "delete", user, {"section_id": section_id})
    return APIResponse(data={"deleted": True})


@router.post("/outline/sections/{section_id}/draft")
async def generate_draft(
    project_id: str, section_id: str, data: DraftGenerateRequest | None = None,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    from app.agents import drafting_agent
    from sqlalchemy import select
    from app.domain.models import OutlineSection

    section = (await db.execute(select(OutlineSection).where(OutlineSection.id == section_id))).scalar_one_or_none()
    enterprise = EnterpriseService(db)
    if section and not await enterprise.can_edit_section(section, user):
        raise HTTPException(403, "仅章节负责人或项目管理员可生成")
    await publish_progress(project_id, "node.start", "开始生成章节初稿", section_id, "generate_draft")
    with progress_context(project_id, "generate_draft"):
        draft = await drafting_agent.generate_draft(project_id, section_id, db)
    await publish_progress(project_id, "node.done", "章节初稿生成完成", section_id, "generate_draft")
    await enterprise.audit("draft", project_id, "generate", user, None, {"section_id": section_id, "draft_id": draft.get("draft_id")})
    return APIResponse(data=draft)


@router.get("/outline/sections/{section_id}/versions")
async def list_draft_versions(
    project_id: str, section_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = DraftService(db)
    versions = await svc.list_versions(section_id)
    return APIResponse(data=[{
        "id": v.id, "section_id": v.section_id, "content": v.content,
        "citations": v.citations, "generated_by": v.generated_by,
        "model_name": v.model_name, "prompt_version": v.prompt_version,
        "status": v.status, "word_count": v.word_count, "created_at": str(v.created_at),
    } for v in versions])


# ── Facts ──
@router.get("/facts")
async def list_facts(
    project_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    from sqlalchemy import select
    result = await db.execute(select(ProjectFact).where(ProjectFact.project_id == project_id))
    facts = result.scalars().all()
    confidence = ConfidenceService(db)
    payload = []
    for f in facts:
        detail = await confidence.fact_confidence(f)
        payload.append({
            "id": f.id, "fact_key": f.fact_key, "fact_value": f.fact_value,
            "source_document_id": f.source_document_id, "source_page": f.source_page,
            "confidence": detail.score, "confidence_detail": detail.as_dict(),
            "confirmation_status": f.confirmation_status,
            "confirmed_by": f.confirmed_by,
            "risk_level": f.risk_level, "version": f.version,
            "created_at": str(f.created_at), "updated_at": str(f.updated_at),
        })
    return APIResponse(data=payload)


@router.get("/confidence/report")
async def confidence_report(
    project_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    return APIResponse(data=await ConfidenceService(db).report(project_id))


@router.post("/confidence/recalculate")
async def recalculate_confidence(
    project_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    result = await ConfidenceService(db).recalculate_project(project_id)
    await EnterpriseService(db).audit("confidence", project_id, "recalculate", user, None, result)
    return APIResponse(data=result)


@router.post("/facts/{fact_id}/confirm")
async def confirm_fact(
    project_id: str, fact_id: str, data: ConfirmationAction,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    result = await db.execute(select(ProjectFact).where(ProjectFact.id == fact_id))
    fact = result.scalar_one_or_none()
    if not fact:
        raise HTTPException(404, "事实不存在")

    if data.action == "approve":
        fact.confirmation_status = ConfirmStatus.CONFIRMED.value
    elif data.action == "modify_and_approve":
        fact.confirmation_status = ConfirmStatus.CONFIRMED.value
        if data.value:
            fact.fact_value = data.value
    elif data.action == "reject":
        fact.confirmation_status = ConfirmStatus.REJECTED.value
    elif data.action == "mark_uncertain":
        fact.confirmation_status = ConfirmStatus.UNCERTAIN.value

    fact.confirmed_by = user["id"]
    fact.version += 1
    await db.flush()
    await EnterpriseService(db).audit("project_fact", project_id, data.action, user, None, {"fact_id": fact.id, "value": fact.fact_value})
    return APIResponse(data={"id": fact.id, "status": fact.confirmation_status})


# ── Addendum conflicts ──
@router.post("/addendum-conflicts/detect")
async def detect_addendum_conflicts(
    project_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    from app.agents.addendum_agent import addendum_agent

    await publish_progress(project_id, "node.start", "开始识别补遗冲突", None, "detect_addendum_conflicts")
    with progress_context(project_id, "detect_addendum_conflicts"):
        result = await addendum_agent.detect_conflicts(project_id, db)
    await publish_progress(project_id, "node.done", "补遗冲突识别完成", f"{result.get('detected_conflicts', 0)} 个冲突", "detect_addendum_conflicts")
    return APIResponse(data=result)


@router.get("/addendum-conflicts")
async def list_addendum_conflicts(
    project_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    result = await db.execute(
        select(ConfirmationTask).where(
            ConfirmationTask.project_id == project_id,
            ConfirmationTask.task_type == "addendum_conflict",
        ).order_by(ConfirmationTask.created_at.desc())
    )
    tasks = result.scalars().all()
    return APIResponse(data=[{
        "id": t.id,
        "status": t.status,
        "resource_id": t.resource_id,
        "candidate_value": t.candidate_value,
        "conflicts": t.conflicts,
        "source_document_id": t.source_document_id,
        "source_page": t.source_page,
        "created_at": str(t.created_at),
    } for t in tasks])


# ── Reviews ──
@router.post("/reviews")
async def run_review(
    project_id: str, review_type: str = "full",
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = ReviewService(db)
    await publish_progress(project_id, "node.start", "开始审查标书", review_type, "review_document")
    with progress_context(project_id, "review_document"):
        review_run = await svc.run_review(project_id, review_type)
    findings = await svc.list_findings(review_run.id)
    await publish_progress(project_id, "node.done", "审查完成", f"{len(findings)} 个发现", "review_document")
    return APIResponse(data={
        "review_run_id": review_run.id, "review_type": review_run.review_type,
        "status": review_run.status, "total_findings": len(findings),
        "high_risk": sum(1 for f in findings if f.risk_level == "high"),
        "findings": [{
            "id": f.id, "finding_type": f.finding_type, "risk_level": f.risk_level,
            "description": f.description, "location": f.location,
            "suggestion": f.suggestion, "status": f.status,
        } for f in findings],
    })


@router.get("/reviews")
async def list_reviews(
    project_id: str,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = ReviewService(db)
    reviews = await svc.list_reviews(project_id)
    return APIResponse(data=[{
        "id": r.id, "review_type": r.review_type, "status": r.status,
        "findings_count": len(r.findings) if r.findings else 0,
        "created_at": str(r.created_at), "completed_at": str(r.completed_at) if r.completed_at else None,
    } for r in reviews])


@router.patch("/reviews/findings/{finding_id}")
async def update_finding(
    project_id: str, finding_id: str,
    status: str = "resolved", ignore_reason: str | None = None,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = ReviewService(db)
    finding = await svc.update_finding(finding_id, status, ignore_reason)
    if not finding:
        raise HTTPException(404, "审查发现不存在")
    return APIResponse(data={"id": finding.id, "status": finding.status})


# ── Exports ──
@router.post("/exports")
async def create_export(
    project_id: str, data: ExportRequest,
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth),
):
    svc = ExportService(db)
    filepath = await svc.export(project_id, data.export_type, data.format)
    await EnterpriseService(db).audit("export", project_id, "create", user, None, {"export_type": data.export_type, "format": data.format, "file_path": filepath})
    return APIResponse(data={
        "export_type": data.export_type, "format": data.format,
        "status": "completed", "file_path": filepath,
    })
