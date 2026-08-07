import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import ConfirmationTask, Document, DocumentPage, ProjectFact, Requirement


@dataclass
class ConfidenceBreakdown:
    score: float
    level: str
    factors: dict
    explanation: str

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "level": self.level,
            "factors": self.factors,
            "explanation": self.explanation,
        }


def clamp(value: float, low: float = 0.05, high: float = 0.99) -> float:
    return max(low, min(high, value))


def level(score: float) -> str:
    if score >= 0.85:
        return "high"
    if score >= 0.65:
        return "medium"
    return "low"


def specificity_score(text: str | None) -> float:
    text = text or ""
    if not text:
        return 0.1
    score = 0.35
    if re.search(r"\d", text):
        score += 0.25
    if re.search(r"\d{4}[年./-]\d{1,2}", text):
        score += 0.2
    if any(unit in text for unit in ("万元", "元", "日历天", "天", "年", "%")):
        score += 0.15
    if len(text.strip()) >= 8:
        score += 0.05
    return clamp(score, 0.1, 1.0)


class ConfidenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def fact_confidence(self, fact: ProjectFact) -> ConfidenceBreakdown:
        source_score, source_hit = await self._source_score(fact.source_document_id, fact.source_page, fact.fact_value)
        conflict_score = await self._conflict_score(fact.project_id, "project_fact", fact.id)
        model_score = self._calibrated_model_score(fact.confidence)
        spec_score = specificity_score(fact.fact_value)
        confirmed_bonus = 1.0 if fact.confirmation_status == "confirmed" else 0.6
        score = clamp(
            model_score * 0.20
            + source_score * 0.30
            + source_hit * 0.23
            + spec_score * 0.13
            + conflict_score * 0.09
            + confirmed_bonus * 0.05
        )
        factors = {
            "model_prior": round(model_score, 3),
            "source_integrity": round(source_score, 3),
            "source_text_hit": round(source_hit, 3),
            "value_specificity": round(spec_score, 3),
            "conflict_free": round(conflict_score, 3),
            "human_confirmation": round(confirmed_bonus, 3),
        }
        return ConfidenceBreakdown(round(score, 3), level(score), factors, self._explain(factors))

    async def requirement_confidence(self, req: Requirement) -> ConfidenceBreakdown:
        source_score, source_hit = await self._source_score(req.source_document_id, req.source_page, req.requirement_text)
        conflict_score = 0.9 if req.review_status != "conflict" else 0.3
        model_score = self._calibrated_model_score(req.confidence)
        spec_score = specificity_score(req.requirement_text)
        structure_score = 0.75
        if req.requirement_type:
            structure_score += 0.1
        if req.mandatory:
            structure_score += 0.05
        if req.evidence_required:
            structure_score += 0.05
        score = clamp(
            model_score * 0.20
            + source_score * 0.30
            + source_hit * 0.24
            + spec_score * 0.10
            + min(structure_score, 1.0) * 0.10
            + conflict_score * 0.06
        )
        factors = {
            "model_prior": round(model_score, 3),
            "source_integrity": round(source_score, 3),
            "source_text_hit": round(source_hit, 3),
            "text_specificity": round(spec_score, 3),
            "structured_fields": round(min(structure_score, 1.0), 3),
            "conflict_free": round(conflict_score, 3),
        }
        return ConfidenceBreakdown(round(score, 3), level(score), factors, self._explain(factors))

    async def recalculate_project(self, project_id: str) -> dict:
        facts = (await self.db.execute(select(ProjectFact).where(ProjectFact.project_id == project_id))).scalars().all()
        reqs = (await self.db.execute(select(Requirement).where(Requirement.project_id == project_id))).scalars().all()
        for fact in facts:
            fact.confidence = (await self.fact_confidence(fact)).score
        for req in reqs:
            req.confidence = (await self.requirement_confidence(req)).score
        await self.db.flush()
        return {
            "facts": len(facts),
            "requirements": len(reqs),
            "average_fact_confidence": round(sum(f.confidence or 0 for f in facts) / len(facts), 3) if facts else 0,
            "average_requirement_confidence": round(sum(r.confidence or 0 for r in reqs) / len(reqs), 3) if reqs else 0,
        }

    async def report(self, project_id: str) -> dict:
        facts = (await self.db.execute(select(ProjectFact).where(ProjectFact.project_id == project_id))).scalars().all()
        reqs = (await self.db.execute(select(Requirement).where(Requirement.project_id == project_id))).scalars().all()
        fact_items = [{"id": f.id, "key": f.fact_key, **(await self.fact_confidence(f)).as_dict()} for f in facts]
        req_items = [{"id": r.id, "type": r.requirement_type, "text": r.requirement_text[:120], **(await self.requirement_confidence(r)).as_dict()} for r in reqs]
        all_scores = [item["score"] for item in fact_items + req_items]
        return {
            "summary": {
                "total_items": len(all_scores),
                "average": round(sum(all_scores) / len(all_scores), 3) if all_scores else 0,
                "high": sum(1 for s in all_scores if s >= 0.85),
                "medium": sum(1 for s in all_scores if 0.65 <= s < 0.85),
                "low": sum(1 for s in all_scores if s < 0.65),
            },
            "facts": fact_items,
            "requirements": req_items,
        }

    async def _source_score(self, doc_id: str | None, page: int | None, text: str | None) -> tuple[float, float]:
        if not doc_id:
            return 0.15, 0.0
        doc = (await self.db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
        if not doc:
            return 0.2, 0.0
        integrity = 0.45
        if doc.parse_status == "completed":
            integrity += 0.25
        if page:
            integrity += 0.15
        if doc.file_hash:
            integrity += 0.1
        hit = 0.0
        if page:
            page_obj = (await self.db.execute(
                select(DocumentPage).where(DocumentPage.document_id == doc_id, DocumentPage.page_number == page)
            )).scalars().first()
            hit = self._text_hit_score(page_obj.text if page_obj else "", text)
        return clamp(integrity), hit

    def _text_hit_score(self, source_text: str | None, extracted_text: str | None) -> float:
        source_text = re.sub(r"\s+", "", source_text or "")
        extracted_text = re.sub(r"\s+", "", extracted_text or "")
        if not source_text or not extracted_text:
            return 0.0
        if extracted_text in source_text:
            return 1.0
        tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]{2,}", extracted_text))
        if not tokens:
            return 0.2
        hits = sum(1 for t in tokens if t in source_text)
        return clamp(hits / len(tokens), 0.0, 1.0)

    async def _conflict_score(self, project_id: str, resource_type: str, resource_id: str) -> float:
        conflict = (await self.db.execute(
            select(ConfirmationTask).where(
                ConfirmationTask.project_id == project_id,
                ConfirmationTask.resource_type == resource_type,
                ConfirmationTask.resource_id == resource_id,
                ConfirmationTask.status == "pending",
            )
        )).scalars().first()
        return 0.35 if conflict else 1.0

    def _calibrated_model_score(self, score: float | None) -> float:
        if score is None:
            return 0.55
        return clamp(float(score), 0.25, 0.92)

    def _explain(self, factors: dict) -> str:
        labels = {
            "model_prior": "模型先验",
            "source_integrity": "来源完整性",
            "source_text_hit": "原文命中",
            "value_specificity": "字段具体性",
            "text_specificity": "文本具体性",
            "conflict_free": "冲突状态",
            "human_confirmation": "人工确认",
            "structured_fields": "结构化字段",
        }
        weak = [name for name, value in factors.items() if value < 0.55]
        if not weak:
            return "来源、原文命中和结构化信息较完整，可信度高。"
        return "需关注：" + "、".join(labels.get(name, name) for name in weak)
