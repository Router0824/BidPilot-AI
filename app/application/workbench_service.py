from datetime import datetime, timezone
from sqlalchemy import select
from app.domain.models import (
    Project, Document, ProjectFact, ConfirmationTask, Requirement,
    OutlineSection, DraftVersion, ReviewRun, ReviewFinding, KnowledgeChunk,
)


async def workbench(db, project_id):
    async def rows(model):
        return list((await db.scalars(select(model).where(model.project_id == project_id))).all())

    project = await db.get(Project, project_id)
    sections = await rows(OutlineSection)
    drafts = {d.id: d for d in (await db.scalars(select(DraftVersion).join(
        OutlineSection, DraftVersion.section_id == OutlineSection.id).where(
        OutlineSection.project_id == project_id))).all()}
    requirements = await rows(Requirement)
    facts = await rows(ProjectFact)
    confirmations = await rows(ConfirmationTask)
    documents = await rows(Document)
    tasks = []

    def add(key, title, target, risk="medium", kind="task"):
        tasks.append(dict(id=key, title=title, target=target, risk=risk, kind=kind))

    if not documents:
        add("upload", "上传招标文件", "", "high", "document")
    if not requirements:
        add("extract", "提取并确认招标要求", "workflow", "high", "requirement")
    for doc in documents:
        if doc.parse_status != "completed":
            add(doc.id, f"解析文件：{doc.name}", "", kind="document")
    for fact in facts:
        if fact.confirmation_status not in ("confirmed", "modified", "rejected"):
            add(fact.id, f"确认事实：{fact.fact_key}", "facts", fact.risk_level, "confirmation")
    for task in confirmations:
        if task.status == "pending":
            add(task.id, f"待确认：{task.task_type}", "workflow", task.risk_level, "confirmation")
    for req in requirements:
        if req.status != "responded":
            add(f"response:{req.id}", f"确认响应：{req.requirement_text}", "requirements", req.risk_level, "requirement")
        if req.requirement_type == "qualification" or req.evidence_required:
            target = next((s for s in sections if s.id == req.response_section_id), None)
            current = drafts.get(target.current_version_id) if target else None
            evidence_ids = [c.get("chunk_id") for c in current.citations or [] if c.get("chunk_id")] if current else []
            usable = False
            for evidence_id in evidence_ids or []:
                chunk = await db.get(KnowledgeChunk, evidence_id)
                if chunk and chunk.is_audited and not chunk.is_expired and (
                    not chunk.valid_until or chunk.valid_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
                ):
                    usable = True
                    break
            if not usable:
                add(req.id, f"补件：{req.evidence_required or req.requirement_text}", "evidence",
                    req.risk_level, "material")
    for section in sections:
        draft = drafts.get(section.current_version_id)
        if not draft or not (draft.content or "").strip():
            add(section.id, f"完成章节：{section.title}", f"outline?section={section.id}", kind="section")
        elif not draft.citations or any(not c.get("source") or not c.get("page") for c in draft.citations):
            add(f"cite:{section.id}", f"补齐引用：{section.title}", f"outline?section={section.id}", kind="citation")
        if draft:
            for cite in draft.citations or []:
                chunk = await db.get(KnowledgeChunk, cite.get("chunk_id") or "")
                if not chunk or not chunk.is_audited or chunk.is_expired or (
                    chunk.valid_until and chunk.valid_until.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)):
                    add(f"invalid-cite:{section.id}", f"更换失效或不存在的引用：{section.title}", f"outline?section={section.id}", "high", "citation")
                    break
        if draft and any(marker in (draft.content or "") for marker in ("待确认", "待补充", "TODO")):
            add(f"placeholder:{section.id}", f"处理占位内容：{section.title}", f"outline?section={section.id}", "high", "placeholder")
    latest = await db.scalar(select(ReviewRun).where(ReviewRun.project_id == project_id).order_by(
        ReviewRun.created_at.desc()).limit(1))
    if latest:
        findings = (await db.scalars(select(ReviewFinding).where(
            ReviewFinding.review_run_id == latest.id, ReviewFinding.status == "open"))).all()
        for finding in findings:
            add(finding.id, finding.description, "reviews", finding.risk_level, "review")
    if not sections:
        add("outline", "建立投标大纲", "workflow", "high", "section")
    if not latest:
        add("review", "完成首次审查", "reviews", "high", "review")
    elif latest.review_type != "full" or latest.status != "completed":
        add("review", "完成全面审查", "reviews", "high", "review")
    elif any(value.replace(tzinfo=timezone.utc) > latest.created_at.replace(tzinfo=timezone.utc)
             for value in [d.created_at for d in drafts.values()] + [f.updated_at for f in facts] + [r.updated_at for r in requirements]):
        add("review-stale", "章节已修改，请重新审查", "reviews", "high", "review")
    tasks.sort(key=lambda item: {"high": 0, "medium": 1, "low": 2}.get(item["risk"], 1))
    deadline = project.deadline.replace(tzinfo=timezone.utc) if project.deadline else None
    return {
        "deadline": deadline.isoformat() if deadline else None,
        "remaining_hours": round((deadline - datetime.now(timezone.utc)).total_seconds() / 3600, 1) if deadline else None,
        "section_count": len(sections),
        "completed_sections": sum(bool(drafts.get(s.current_version_id) and (drafts[s.current_version_id].content or "").strip()) for s in sections),
        "tasks": tasks, "missing_materials": sum(t["kind"] == "material" for t in tasks),
        "pending_confirmations": sum(t["kind"] == "confirmation" for t in tasks),
        "export_ready": not tasks,
    }
