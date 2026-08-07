import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.domain.models import (
    ReviewRun, ReviewFinding, Requirement, DraftVersion, OutlineSection,
    ProjectFact, RequirementStatus, RiskLevel, ConfirmStatus
)
from app.schemas import ExportRequest


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_reviews(self, project_id: str) -> list[ReviewRun]:
        result = await self.db.execute(
            select(ReviewRun).where(ReviewRun.project_id == project_id).order_by(ReviewRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def run_review(self, project_id: str, review_type: str = "full") -> ReviewRun:
        review_run = ReviewRun(project_id=project_id, review_type=review_type, status="running")
        self.db.add(review_run)
        await self.db.flush()

        findings = []

        if review_type in ("full", "coverage"):
            findings += await self._check_coverage(project_id, review_run.id)
        if review_type in ("full", "consistency"):
            findings += await self._check_consistency(project_id, review_run.id)
        if review_type in ("full", "citation"):
            findings += await self._check_citations(project_id, review_run.id)
        if review_type in ("full", "overcommit"):
            findings += await self._check_overcommit(project_id, review_run.id)

        review_run.findings = [f.id for f in findings]
        review_run.status = "completed"
        await self.db.flush()
        return review_run

    async def _check_coverage(self, project_id: str, review_run_id: str) -> list[ReviewFinding]:
        findings = []
        result = await self.db.execute(
            select(Requirement).where(
                and_(Requirement.project_id == project_id, Requirement.status != RequirementStatus.RESPONDED.value)
            )
        )
        uncovered = result.scalars().all()
        for req in uncovered:
            f = ReviewFinding(
                review_run_id=review_run_id,
                finding_type="uncovered_requirement",
                risk_level=req.risk_level,
                description=f"要求未响应：{req.requirement_text[:200]}",
                location=f"requirement:{req.id}",
                suggestion="请确认是否有意在标书中省略此要求，或为要求分配响应章节",
            )
            self.db.add(f)
            findings.append(f)
        return findings

    async def _check_consistency(self, project_id: str, review_run_id: str) -> list[ReviewFinding]:
        findings = []
        facts_result = await self.db.execute(
            select(ProjectFact).where(ProjectFact.project_id == project_id)
        )
        facts = {f.fact_key: f.fact_value for f in facts_result.scalars().all()}

        sections_result = await self.db.execute(
            select(OutlineSection).where(OutlineSection.project_id == project_id)
        )
        sections = sections_result.scalars().all()

        for section in sections:
            if section.current_version_id:
                draft = (await self.db.execute(
                    select(DraftVersion).where(DraftVersion.id == section.current_version_id)
                )).scalar_one_or_none()
                if draft and draft.content:
                    for key, val in facts.items():
                        if val and val not in draft.content:
                            f = ReviewFinding(
                                review_run_id=review_run_id,
                                finding_type="fact_inconsistency",
                                risk_level="medium",
                                description=f"章节「{section.title}」中未发现项目事实「{key}」({val})",
                                location=f"section:{section.id}",
                                suggestion=f"请确认章节中是否包含 {key} 相关信息",
                            )
                            self.db.add(f)
                            findings.append(f)
        return findings

    async def _check_citations(self, project_id: str, review_run_id: str) -> list[ReviewFinding]:
        findings = []
        sections_result = await self.db.execute(
            select(OutlineSection).where(
                and_(OutlineSection.project_id == project_id, OutlineSection.current_version_id.isnot(None))
            )
        )
        for section in sections_result.scalars().all():
            draft = (await self.db.execute(
                select(DraftVersion).where(DraftVersion.id == section.current_version_id)
            )).scalar_one_or_none()
            if draft and draft.citations:
                for cite in draft.citations:
                    if cite.get("status") == "unverified":
                        f = ReviewFinding(
                            review_run_id=review_run_id,
                            finding_type="unverified_citation",
                            risk_level="medium",
                            description=f"章节「{section.title}」中存在未验证引用：{cite.get('source', '')}",
                            location=f"section:{section.id}",
                            suggestion="请确认引用来源的有效性",
                        )
                        self.db.add(f)
                        findings.append(f)
        return findings

    async def _check_overcommit(self, project_id: str, review_run_id: str) -> list[ReviewFinding]:
        findings = []
        overcommit_keywords = ["准确率", "99", "100%", "零故障", "绝对安全", "万无一失", "保证中标"]
        sections_result = await self.db.execute(
            select(OutlineSection).where(
                and_(OutlineSection.project_id == project_id, OutlineSection.current_version_id.isnot(None))
            )
        )
        for section in sections_result.scalars().all():
            draft = (await self.db.execute(
                select(DraftVersion).where(DraftVersion.id == section.current_version_id)
            )).scalar_one_or_none()
            if draft and draft.content:
                for kw in overcommit_keywords:
                    if kw in draft.content:
                        f = ReviewFinding(
                            review_run_id=review_run_id,
                            finding_type="overcommit",
                            risk_level="high",
                            description=f"章节「{section.title}」中存在过度承诺嫌疑：包含「{kw}」",
                            location=f"section:{section.id}",
                            suggestion="请确认该表述是否有企业材料支撑，若无请删除或修改",
                        )
                        self.db.add(f)
                        findings.append(f)
                        break
        return findings

    async def list_findings(self, review_run_id: str) -> list[ReviewFinding]:
        result = await self.db.execute(
            select(ReviewFinding).where(ReviewFinding.review_run_id == review_run_id)
        )
        return list(result.scalars().all())

    async def update_finding(self, finding_id: str, status: str, ignore_reason: str | None = None) -> ReviewFinding | None:
        result = await self.db.execute(select(ReviewFinding).where(ReviewFinding.id == finding_id))
        finding = result.scalar_one_or_none()
        if not finding:
            return None
        finding.status = status
        if ignore_reason:
            finding.ignore_reason = ignore_reason
        await self.db.flush()
        return finding


class ExportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def export(self, project_id: str, export_type: str, fmt: str) -> str:
        import os
        export_dir = os.path.join("uploads", project_id, "exports")
        os.makedirs(export_dir, exist_ok=True)

        if export_type == "requirements":
            return await self._export_requirements(project_id, export_dir, fmt)
        elif export_type == "outline":
            return await self._export_outline(project_id, export_dir, fmt)
        elif export_type == "full_document":
            return await self._export_full(project_id, export_dir, fmt)
        elif export_type == "risk_list":
            return await self._export_risk_list(project_id, export_dir, fmt)
        else:
            return await self._export_draft(project_id, export_dir, fmt)

    async def _export_requirements(self, project_id: str, export_dir: str, fmt: str) -> str:
        result = await self.db.execute(
            select(Requirement).where(Requirement.project_id == project_id).order_by(Requirement.risk_level.desc())
        )
        reqs = result.scalars().all()

        if fmt == "docx":
            filepath = f"{export_dir}/requirements.docx"
            self._write_requirements_docx(filepath, reqs)
            return filepath
        if fmt == "markdown":
            lines = ["# 要求与风险矩阵\n"]
            lines.append("| ID | 类型 | 风险 | 硬性 | 要求内容 | 状态 |")
            lines.append("|----|------|------|------|----------|------|")
            for r in reqs:
                mandatory = "是" if r.mandatory else "否"
                lines.append(f"| {r.id[:8]} | {r.requirement_type} | {r.risk_level} | {mandatory} | {r.requirement_text[:100]} | {r.status} |")
            content = "\n".join(lines)
        elif fmt == "xlsx":
            content = await self._export_xlsx(reqs, ["ID", "类型", "风险", "硬性", "要求内容", "状态"],
                lambda r: [r.id[:8], r.requirement_type, r.risk_level, "是" if r.mandatory else "否", r.requirement_text[:100], r.status])
        else:
            content = "\n".join(f"{r.requirement_type}\t{r.risk_level}\t{r.requirement_text}" for r in reqs)

        filepath = f"{export_dir}/requirements.{fmt}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    async def _export_outline(self, project_id: str, export_dir: str, fmt: str) -> str:
        result = await self.db.execute(
            select(OutlineSection).where(OutlineSection.project_id == project_id).order_by(OutlineSection.sort_order)
        )
        sections = result.scalars().all()
        if fmt == "docx":
            filepath = f"{export_dir}/outline.docx"
            self._write_outline_docx(filepath, sections)
            return filepath
        lines = ["# 技术标大纲\n"]
        for s in sections:
            indent = "  " * (s.level - 1)
            lines.append(f"{indent}- {s.title}")
        content = "\n".join(lines)
        filepath = f"{export_dir}/outline.{fmt}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    async def _export_full(self, project_id: str, export_dir: str, fmt: str) -> str:
        result = await self.db.execute(
            select(OutlineSection).where(OutlineSection.project_id == project_id).order_by(OutlineSection.sort_order)
        )
        sections = result.scalars().all()
        if fmt == "docx":
            filepath = f"{export_dir}/full_document.docx"
            await self._write_full_docx(filepath, sections)
            return filepath
        lines = ["# 技术标书\n"]
        for s in sections:
            prefix = "#" * min(s.level, 6)
            lines.append(f"\n{prefix} {s.title}\n")
            if s.current_version_id:
                draft = (await self.db.execute(
                    select(DraftVersion).where(DraftVersion.id == s.current_version_id)
                )).scalar_one_or_none()
                if draft and draft.content:
                    lines.append(draft.content)
                    lines.append("")
        content = "\n".join(lines)
        filepath = f"{export_dir}/full_document.{fmt}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    async def _export_risk_list(self, project_id: str, export_dir: str, fmt: str) -> str:
        result = await self.db.execute(
            select(Requirement).where(
                and_(Requirement.project_id == project_id, Requirement.risk_level.in_(["high", "medium"]))
            ).order_by(Requirement.risk_level.desc())
        )
        reqs = result.scalars().all()
        if fmt == "docx":
            filepath = f"{export_dir}/risk_list.docx"
            self._write_risk_list_docx(filepath, reqs)
            return filepath
        lines = ["# 风险清单\n"]
        for r in reqs:
            lines.append(f"## [{r.risk_level.upper()}] {r.requirement_text[:200]}")
            lines.append(f"- 类型：{r.requirement_type}")
            lines.append(f"- 来源：{r.source_document_id} 第{r.source_page}页")
            lines.append(f"- 状态：{r.status}")
            lines.append("")
        content = "\n".join(lines)
        filepath = f"{export_dir}/risk_list.{fmt}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    async def _export_draft(self, project_id: str, export_dir: str, fmt: str) -> str:
        return await self._export_full(project_id, export_dir, fmt)

    async def _export_xlsx(self, items, headers, row_fn) -> str:
        rows = ["\t".join(headers)]
        rows.extend("\t".join(str(c) for c in row_fn(i)) for i in items)
        return "\n".join(rows)

    def _new_docx(self):
        from docx import Document as DocxDocument  # noqa: N811
        from docx.oxml.ns import qn

        doc = DocxDocument()
        styles = doc.styles
        for style_name in ("Normal", "Heading 1", "Heading 2", "Heading 3"):
            style = styles[style_name]
            style.font.name = "Noto Serif CJK SC"
            style._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Serif CJK SC")
        return doc

    def _add_markdownish_paragraphs(self, doc, content: str) -> None:
        from docx.enum.text import WD_COLOR_INDEX

        for line in (content or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("### "):
                doc.add_heading(stripped[4:], level=3)
            elif stripped.startswith("## "):
                doc.add_heading(stripped[3:], level=2)
            elif stripped.startswith("# "):
                doc.add_heading(stripped[2:], level=1)
            else:
                paragraph = doc.add_paragraph()
                cursor = 0
                for match in re.finditer(r"【.+?】", stripped):
                    if match.start() > cursor:
                        paragraph.add_run(stripped[cursor:match.start()])
                    run = paragraph.add_run(match.group(0))
                    run.font.highlight_color = WD_COLOR_INDEX.YELLOW
                    cursor = match.end()
                if cursor < len(stripped):
                    paragraph.add_run(stripped[cursor:])

    def _write_requirements_docx(self, filepath: str, reqs: list[Requirement]) -> None:
        doc = self._new_docx()
        doc.add_heading("要求与风险矩阵", level=1)
        table = doc.add_table(rows=1, cols=6)
        table.style = "Table Grid"
        headers = ["ID", "类型", "风险", "硬性", "要求内容", "状态"]
        for idx, header in enumerate(headers):
            table.rows[0].cells[idx].text = header
        for req in reqs:
            cells = table.add_row().cells
            values = [req.id[:8], req.requirement_type, req.risk_level, "是" if req.mandatory else "否", req.requirement_text[:300], req.status]
            for idx, value in enumerate(values):
                cells[idx].text = str(value)
        doc.save(filepath)

    def _write_outline_docx(self, filepath: str, sections: list[OutlineSection]) -> None:
        doc = self._new_docx()
        doc.add_heading("技术标大纲", level=1)
        for section in sections:
            doc.add_paragraph(f"{'  ' * max(0, section.level - 1)}{section.sort_order}. {section.title}")
        doc.save(filepath)

    async def _write_full_docx(self, filepath: str, sections: list[OutlineSection]) -> None:
        doc = self._new_docx()
        doc.add_heading("技术标书", level=1)
        for section in sections:
            doc.add_heading(section.title, level=min(max(section.level, 1), 3))
            if section.current_version_id:
                draft = (await self.db.execute(
                    select(DraftVersion).where(DraftVersion.id == section.current_version_id)
                )).scalar_one_or_none()
                if draft and draft.content:
                    self._add_markdownish_paragraphs(doc, draft.content)
                if draft and draft.citations:
                    doc.add_paragraph("引用来源：")
                    for cite in draft.citations:
                        doc.add_paragraph(
                            f"{cite.get('source', '')} 第{cite.get('page', '-')}页：{cite.get('snippet', '')}",
                            style="List Bullet",
                        )
        doc.save(filepath)

    def _write_risk_list_docx(self, filepath: str, reqs: list[Requirement]) -> None:
        doc = self._new_docx()
        doc.add_heading("风险清单", level=1)
        for req in reqs:
            doc.add_heading(f"[{req.risk_level.upper()}] {req.requirement_text[:80]}", level=2)
            doc.add_paragraph(f"类型：{req.requirement_type}")
            doc.add_paragraph(f"来源：{req.source_document_id or '-'} 第{req.source_page or '-'}页")
            doc.add_paragraph(f"状态：{req.status}")
        doc.save(filepath)
