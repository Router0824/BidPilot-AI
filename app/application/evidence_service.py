from __future__ import annotations

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    CoverageStatus,
    Document,
    DocumentPage,
    DraftVersion,
    KnowledgeChunk,
    OutlineSection,
    Requirement,
    RequirementEvidenceLink,
    ReviewFinding,
    ScoringItem,
)


class EvidenceGraphService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def rebuild_project_links(self, project_id: str) -> dict:
        await self.db.execute(delete(RequirementEvidenceLink).where(RequirementEvidenceLink.project_id == project_id))
        requirements = list((await self.db.execute(
            select(Requirement).where(Requirement.project_id == project_id).order_by(Requirement.created_at)
        )).scalars().all())
        created = 0
        for req in requirements:
            link = await self._build_link(req)
            self.db.add(link)
            created += 1
        await self.db.flush()
        return {"rebuilt_links": created}

    async def list_matrix(self, project_id: str) -> list[dict]:
        await self._ensure_links(project_id)
        rows = list((await self.db.execute(
            select(RequirementEvidenceLink).where(RequirementEvidenceLink.project_id == project_id)
            .order_by(RequirementEvidenceLink.risk_level.desc(), RequirementEvidenceLink.created_at)
        )).scalars().all())
        req_map = await self._requirement_map(project_id)
        doc_map = await self._document_map(project_id)
        knowledge_ids = sorted({
            kid for row in rows for kid in (row.knowledge_evidence_ids or [])
        })
        knowledge_map = await self._knowledge_map(knowledge_ids)
        return [
            self._serialize_row(row, req_map.get(row.requirement_id), doc_map, knowledge_map)
            for row in rows
        ]

    async def evidence_chain(self, project_id: str, requirement_id: str) -> dict | None:
        await self._ensure_links(project_id)
        row = (await self.db.execute(
            select(RequirementEvidenceLink).where(
                RequirementEvidenceLink.project_id == project_id,
                RequirementEvidenceLink.requirement_id == requirement_id,
            )
        )).scalar_one_or_none()
        if not row:
            return None
        req = (await self.db.execute(select(Requirement).where(Requirement.id == requirement_id))).scalar_one_or_none()
        docs = await self._document_map(project_id)
        knowledge_map = await self._knowledge_map(row.knowledge_evidence_ids or [])
        review_issues = []
        if row.review_issue_ids:
            review_issues = list((await self.db.execute(
                select(ReviewFinding).where(ReviewFinding.id.in_(row.review_issue_ids))
            )).scalars().all())
        draft = None
        if row.generated_content_id:
            draft = (await self.db.execute(
                select(DraftVersion).where(DraftVersion.id == row.generated_content_id)
            )).scalar_one_or_none()
        return {
            "row": self._serialize_row(row, req, docs, knowledge_map),
            "source_document": self._serialize_document(docs.get(row.source_document_id)),
            "source": {
                "page": row.source_page,
                "section": row.source_section,
                "quote": row.source_quote,
            },
            "target_section": {
                "id": row.target_section_id,
                "title": row.target_section_title,
            },
            "knowledge_evidence": [
                self._serialize_knowledge(knowledge_map[kid])
                for kid in (row.knowledge_evidence_ids or [])
                if kid in knowledge_map
            ],
            "generated_content": {
                "id": draft.id,
                "content": draft.content,
                "citations": draft.citations,
                "created_at": str(draft.created_at),
            } if draft else None,
            "review_issues": [
                {
                    "id": issue.id,
                    "issue_type": issue.finding_type,
                    "risk_level": issue.risk_level,
                    "description": issue.description,
                    "suggestion": issue.suggestion,
                    "status": issue.status,
                }
                for issue in review_issues
            ],
        }

    async def _ensure_links(self, project_id: str) -> None:
        existing = (await self.db.execute(
            select(RequirementEvidenceLink.id).where(RequirementEvidenceLink.project_id == project_id).limit(1)
        )).scalar_one_or_none()
        if not existing:
            await self.rebuild_project_links(project_id)

    async def _build_link(self, req: Requirement) -> RequirementEvidenceLink:
        page = await self._source_page(req)
        source_quote = self._quote_for_requirement(page.text if page else "", req.requirement_text)
        section = await self._target_section(req)
        draft = await self._current_draft(section) if section else None
        review_issue_ids = await self._review_issue_ids(req, section)
        knowledge_ids = self._knowledge_ids_from_draft(draft)
        score_weight = await self._score_weight(req)
        coverage_status = self._coverage_status(req, section, draft, review_issue_ids)
        return RequirementEvidenceLink(
            project_id=req.project_id,
            requirement_id=req.id,
            source_document_id=req.source_document_id,
            source_page=req.source_page,
            source_section=self._infer_section(page.text if page else "", req.requirement_text),
            source_quote=source_quote,
            requirement_type=req.requirement_type,
            score_weight=score_weight,
            mandatory=req.mandatory,
            risk_level=req.risk_level,
            confidence=req.confidence,
            target_section_id=section.id if section else req.response_section_id,
            target_section_title=section.title if section else None,
            knowledge_evidence_ids=knowledge_ids,
            generated_content_id=draft.id if draft else None,
            review_issue_ids=review_issue_ids,
            coverage_status=coverage_status,
            human_confirmed=req.status in ("confirmed", "responded"),
        )

    async def _source_page(self, req: Requirement) -> DocumentPage | None:
        if not req.source_document_id:
            return None
        result = await self.db.execute(
            select(DocumentPage).where(
                DocumentPage.document_id == req.source_document_id,
                DocumentPage.page_number == (req.source_page or 1),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def _target_section(self, req: Requirement) -> OutlineSection | None:
        if req.response_section_id:
            section = (await self.db.execute(
                select(OutlineSection).where(OutlineSection.id == req.response_section_id)
            )).scalar_one_or_none()
            if section:
                return section
        sections = list((await self.db.execute(
            select(OutlineSection).where(OutlineSection.project_id == req.project_id).order_by(OutlineSection.sort_order)
        )).scalars().all())
        type_keywords = {
            "qualification": ("资质", "资格", "案例", "人员"),
            "technical": ("技术", "架构", "方案", "需求"),
            "commercial": ("商务", "报价", "付款"),
            "delivery": ("实施", "交付", "验收", "工期"),
            "format": ("格式", "装订", "盖章"),
            "scoring": ("评分", "响应"),
        }
        keywords = type_keywords.get(req.requirement_type, ())
        for section in sections:
            if any(keyword in section.title for keyword in keywords):
                return section
        return sections[0] if sections else None

    async def _current_draft(self, section: OutlineSection) -> DraftVersion | None:
        if not section.current_version_id:
            return None
        return (await self.db.execute(
            select(DraftVersion).where(DraftVersion.id == section.current_version_id)
        )).scalar_one_or_none()

    async def _review_issue_ids(self, req: Requirement, section: OutlineSection | None) -> list[str]:
        locations = [f"requirement:{req.id}"]
        if section:
            locations.append(f"section:{section.id}")
        result = await self.db.execute(
            select(ReviewFinding).where(
                ReviewFinding.location.in_(locations),
                ReviewFinding.status == "open",
            )
        )
        return [item.id for item in result.scalars().all()]

    async def _score_weight(self, req: Requirement) -> float | None:
        result = await self.db.execute(
            select(ScoringItem).where(
                ScoringItem.project_id == req.project_id,
                ScoringItem.criteria.isnot(None),
            )
        )
        req_text = req.requirement_text or ""
        best_score = None
        for item in result.scalars().all():
            criteria = item.criteria or item.title or ""
            if criteria and (criteria[:20] in req_text or req_text[:20] in criteria):
                best_score = item.score
                break
        return best_score

    def _coverage_status(
        self,
        req: Requirement,
        section: OutlineSection | None,
        draft: DraftVersion | None,
        review_issue_ids: list[str],
    ) -> str:
        if review_issue_ids:
            return CoverageStatus.CONFLICTED.value
        if req.status == "missing":
            return CoverageStatus.MISSING.value
        if req.status == "pending" and req.risk_level == "high":
            return CoverageStatus.PENDING_CONFIRMATION.value
        if draft and req.requirement_text and req.requirement_text[:20] in (draft.content or ""):
            return CoverageStatus.COVERED.value
        if draft or section or req.response_section_id or req.status in ("confirmed", "responded"):
            return CoverageStatus.PARTIALLY_COVERED.value
        return CoverageStatus.MISSING.value

    def _knowledge_ids_from_draft(self, draft: DraftVersion | None) -> list[str]:
        if not draft or not draft.citations:
            return []
        ids = []
        for cite in draft.citations:
            chunk_id = cite.get("chunk_id")
            if chunk_id and chunk_id not in ids:
                ids.append(chunk_id)
        return ids

    def _quote_for_requirement(self, page_text: str, requirement_text: str) -> str:
        text = page_text or ""
        req = (requirement_text or "").strip()
        if not text:
            return req[:300]
        probe = req[:30]
        index = text.find(probe) if probe else -1
        if index < 0:
            terms = [term for term in ("必须", "须", "应", "不得", "工期", "资格", "评分", "售后") if term in req]
            index = min([text.find(term) for term in terms if text.find(term) >= 0] or [-1])
        if index < 0:
            return text[:300]
        return text[max(0, index - 80): index + min(len(req), 220)]

    def _infer_section(self, page_text: str, requirement_text: str) -> str | None:
        text = page_text or ""
        index = text.find((requirement_text or "")[:20])
        lines = text[:index if index >= 0 else len(text)].splitlines()
        for line in reversed(lines):
            stripped = line.strip(" #：:")
            if stripped and len(stripped) <= 80 and any(marker in stripped for marker in ("要求", "评分", "资格", "技术", "商务", "服务")):
                return stripped
        return None

    async def _requirement_map(self, project_id: str) -> dict[str, Requirement]:
        return {
            req.id: req for req in (await self.db.execute(
                select(Requirement).where(Requirement.project_id == project_id)
            )).scalars().all()
        }

    async def _document_map(self, project_id: str) -> dict[str, Document]:
        return {
            doc.id: doc for doc in (await self.db.execute(
                select(Document).where(Document.project_id == project_id)
            )).scalars().all()
        }

    async def _knowledge_map(self, ids: list[str]) -> dict[str, KnowledgeChunk]:
        if not ids:
            return {}
        return {
            chunk.id: chunk for chunk in (await self.db.execute(
                select(KnowledgeChunk).where(KnowledgeChunk.id.in_(ids))
            )).scalars().all()
        }

    def _serialize_row(
        self,
        row: RequirementEvidenceLink,
        req: Requirement | None,
        docs: dict[str, Document],
        knowledge: dict[str, KnowledgeChunk],
    ) -> dict:
        return {
            "link_id": row.id,
            "requirement_id": row.requirement_id,
            "requirement_text": req.requirement_text if req else "",
            "source_document_id": row.source_document_id,
            "source_document_name": docs.get(row.source_document_id).name if docs.get(row.source_document_id) else "",
            "source_page": row.source_page,
            "source_section": row.source_section,
            "source_quote": row.source_quote,
            "requirement_type": row.requirement_type,
            "score_weight": row.score_weight,
            "mandatory": row.mandatory,
            "risk_level": row.risk_level,
            "confidence": row.confidence,
            "target_section_id": row.target_section_id,
            "target_section_title": row.target_section_title,
            "knowledge_evidence_ids": row.knowledge_evidence_ids or [],
            "knowledge_evidence_names": [
                knowledge[kid].material_name for kid in (row.knowledge_evidence_ids or []) if kid in knowledge
            ],
            "generated_content_id": row.generated_content_id,
            "review_issue_ids": row.review_issue_ids or [],
            "coverage_status": row.coverage_status,
            "human_confirmed": row.human_confirmed,
            "updated_at": str(row.updated_at),
        }

    def _serialize_document(self, doc: Document | None) -> dict | None:
        if not doc:
            return None
        return {
            "id": doc.id,
            "name": doc.name,
            "document_type": doc.document_type,
            "file_hash": doc.file_hash,
            "page_count": doc.page_count,
        }

    def _serialize_knowledge(self, chunk: KnowledgeChunk) -> dict:
        return {
            "id": chunk.id,
            "material_name": chunk.material_name,
            "material_type": chunk.material_type,
            "source_page": chunk.source_page,
            "title_path": chunk.title_path,
            "content": chunk.content,
            "is_audited": chunk.is_audited,
        }
