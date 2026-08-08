import json
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import agents
from app.agents import MockLLMGateway
from app.application.knowledge_service import KnowledgeIndexService, tokenize
from app.domain.models import (
    ConsultationMessage,
    ConsultationSession,
    Document,
    DocumentPage,
    Project,
    ProjectFact,
    Requirement,
)


ROLE_GUIDANCE = {
    "admin": "从项目全局、权限与风险闭环角度给出建议。",
    "project_admin": "从投标经理视角，优先关注进度、响应策略、风险取舍与责任分配。",
    "writer": "从编制人员视角，给出可直接写入标书的结构化建议和证据清单。",
    "reviewer": "从审核人员视角，指出合规风险、缺漏项和需复核的原文依据。",
}


class ConsultationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_sessions(self, project_id: str) -> list[ConsultationSession]:
        result = await self.db.execute(
            select(ConsultationSession)
            .where(ConsultationSession.project_id == project_id)
            .order_by(ConsultationSession.updated_at.desc())
        )
        return result.scalars().all()

    async def create_session(self, project_id: str, user: dict, title: str | None = None) -> ConsultationSession:
        session = ConsultationSession(
            project_id=project_id,
            title=(title or "新咨询")[:255],
            created_by=user["id"],
            created_by_name=user.get("display_name") or user.get("username"),
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def list_messages(self, session_id: str) -> list[ConsultationMessage]:
        result = await self.db.execute(
            select(ConsultationMessage)
            .where(ConsultationMessage.session_id == session_id)
            .order_by(ConsultationMessage.created_at.asc())
        )
        return result.scalars().all()

    async def ask(self, project_id: str, session_id: str, question: str, user: dict) -> dict:
        session = await self._get_session(project_id, session_id)
        if not session:
            raise ValueError("咨询会话不存在")

        question = question.strip()
        user_msg = ConsultationMessage(session_id=session_id, role="user", content=question, citations=[], meta={})
        self.db.add(user_msg)
        await self.db.flush()

        history = await self.list_messages(session_id)
        context, citations = await self._build_context(project_id, question)
        answer = await self._answer_with_llm(question, history[-8:], context, citations, user)
        assistant_msg = ConsultationMessage(
            session_id=session_id,
            role="assistant",
            content=answer["answer"],
            citations=citations,
            meta={
                "role": user.get("role"),
                "confidence": answer["confidence"],
                "followups": answer["followups"],
                "used_context": len(citations),
            },
        )
        self.db.add(assistant_msg)
        session.updated_at = datetime.now(timezone.utc)
        if session.title == "新咨询":
            session.title = question[:40]
        await self.db.flush()
        return {
            "message": self._message_dict(assistant_msg),
            "session": self._session_dict(session),
            "confidence": answer["confidence"],
            "followups": answer["followups"],
        }

    def _session_dict(self, session: ConsultationSession) -> dict:
        return {
            "id": session.id,
            "project_id": session.project_id,
            "title": session.title,
            "created_by_name": session.created_by_name,
            "created_at": str(session.created_at),
            "updated_at": str(session.updated_at),
        }

    def _message_dict(self, msg: ConsultationMessage) -> dict:
        return {
            "id": msg.id,
            "session_id": msg.session_id,
            "role": msg.role,
            "content": msg.content,
            "citations": msg.citations or [],
            "meta": msg.meta or {},
            "created_at": str(msg.created_at),
        }

    async def _get_session(self, project_id: str, session_id: str) -> ConsultationSession | None:
        return (await self.db.execute(
            select(ConsultationSession).where(
                ConsultationSession.id == session_id,
                ConsultationSession.project_id == project_id,
            )
        )).scalar_one_or_none()

    async def _build_context(self, project_id: str, question: str) -> tuple[dict, list[dict]]:
        project = (await self.db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        facts = (await self.db.execute(select(ProjectFact).where(ProjectFact.project_id == project_id).limit(30))).scalars().all()
        reqs = (await self.db.execute(select(Requirement).where(Requirement.project_id == project_id).limit(40))).scalars().all()
        doc_citations = await self._document_citations(project_id, question)
        knowledge = await KnowledgeIndexService(self.db).retrieve(question, limit=5, audited_only=False)

        citations = doc_citations + [
            {
                "type": "knowledge",
                "source": item["material_name"],
                "page": item.get("source_page"),
                "snippet": item["content_snippet"],
                "score": item["score"],
            }
            for item in knowledge
            if item.get("score", 0) > 0
        ]
        citations = self._dedupe_citations(citations)[:10]
        context = {
            "project": {
                "id": project.id if project else project_id,
                "name": project.name if project else "",
                "type": project.project_type if project else "",
                "deadline": str(project.deadline) if project and project.deadline else "",
            },
            "facts": [{"key": f.fact_key, "value": f.fact_value, "confidence": f.confidence} for f in facts],
            "requirements": [
                {
                    "text": r.requirement_text,
                    "type": r.requirement_type,
                    "mandatory": r.mandatory,
                    "risk": r.risk_level,
                    "source_page": r.source_page,
                }
                for r in reqs
            ],
            "citations": citations,
        }
        return context, citations

    async def _document_citations(self, project_id: str, question: str) -> list[dict]:
        terms = set(tokenize(question))
        if not terms:
            return []
        result = await self.db.execute(
            select(DocumentPage, Document)
            .join(Document, DocumentPage.document_id == Document.id)
            .where(Document.project_id == project_id)
            .limit(300)
        )
        scored = []
        for page, doc in result.all():
            text = page.text or ""
            page_terms = set(tokenize(text))
            hits = terms & page_terms
            if not hits:
                continue
            score = len(hits) / max(1, len(terms))
            snippet = self._best_snippet(text, hits)
            scored.append((score, {
                "type": "document",
                "source": doc.name,
                "document_id": doc.id,
                "page": page.page_number,
                "snippet": snippet,
                "score": round(score, 3),
            }))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in scored[:5]]

    def _best_snippet(self, text: str, hits: set[str]) -> str:
        clean = re.sub(r"\s+", " ", text or "")
        if not clean:
            return ""
        first_positions = [clean.find(term) for term in hits if clean.find(term) >= 0]
        pos = min(first_positions) if first_positions else 0
        start = max(0, pos - 90)
        return clean[start:start + 260]

    def _dedupe_citations(self, citations: list[dict]) -> list[dict]:
        deduped = []
        seen = set()
        seen_snippets = set()
        for item in citations:
            source = str(item.get("source") or "").strip()
            snippet = re.sub(r"\s+", " ", str(item.get("snippet") or "")).strip()
            snippet_key = snippet[:220]
            key = (
                str(item.get("type") or ""),
                source,
                str(item.get("page") or ""),
                snippet_key,
            )
            if key in seen or (snippet_key and snippet_key in seen_snippets):
                continue
            seen.add(key)
            if snippet_key:
                seen_snippets.add(snippet_key)
            deduped.append(item)
        return deduped

    async def _answer_with_llm(
        self,
        question: str,
        history: list[ConsultationMessage],
        context: dict,
        citations: list[dict],
        user: dict,
    ) -> dict:
        role = user.get("role") or "writer"
        base_confidence = self._context_confidence(citations)
        llm_gateway = agents.active_llm_gateway
        if llm_gateway and not isinstance(llm_gateway, MockLLMGateway):
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是投标项目咨询专家。只输出JSON，字段为 answer, confidence, followups。"
                        "回答必须基于给定项目事实、招标要求、知识库和引用片段；不能确定时明确说明。"
                        f"当前用户角色建议：{ROLE_GUIDANCE.get(role, ROLE_GUIDANCE['writer'])}"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "history": [{"role": m.role, "content": m.content} for m in history],
                            "context": context,
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
            try:
                data = await llm_gateway.call("consultation_answer", messages, "json", max_tokens=2200, temperature=0.2)
                answer = str(data.get("answer") or "").strip()
                if answer:
                    confidence = min(float(data.get("confidence") or base_confidence), base_confidence + 0.12)
                    return {
                        "answer": answer,
                        "confidence": round(max(0.2, min(confidence, 0.96)), 3),
                        "followups": list(data.get("followups") or [])[:3],
                    }
            except Exception:
                pass

        bullets = []
        if context["requirements"]:
            bullets.append(f"已匹配到 {len(context['requirements'])} 条项目要求，建议优先核对硬性要求和高风险条款。")
        if citations:
            bullets.append("可追溯资料已附在下方，建议以文档页码和知识库片段作为回复依据。")
        bullets.append(ROLE_GUIDANCE.get(role, ROLE_GUIDANCE["writer"]))
        return {
            "answer": "\n".join(f"- {item}" for item in bullets),
            "confidence": base_confidence,
            "followups": ["需要我按风险等级拆解吗？", "是否要生成可写入标书的回复段落？"],
        }

    def _context_confidence(self, citations: list[dict]) -> float:
        if not citations:
            return 0.35
        doc_count = sum(1 for item in citations if item["type"] == "document")
        avg_score = sum(float(item.get("score") or 0) for item in citations) / len(citations)
        return round(min(0.9, 0.42 + doc_count * 0.08 + avg_score * 0.35), 3)
