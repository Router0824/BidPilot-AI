import json
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.runtime_config import get_runtime_llm_config
from app.observability.progress import publish_current


REQUIREMENT_TYPES = {"qualification", "technical", "commercial", "scoring", "delivery", "format"}
RISK_LEVELS = {"high", "medium", "low"}


def _extract_json_object(content: str) -> dict[str, Any]:
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _truncate_text(text: str, max_chars: int = 12000) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n\n...[中间内容已截断]...\n\n{tail}"


def _chunk_text(text: str, chunk_size: int = 9000, max_chunks: int = 4) -> list[str]:
    text = text or ""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text) and len(chunks) < max_chunks:
        chunks.append(text[start:start + chunk_size])
        start += chunk_size
    return chunks


def _clean_risk(value: str | None, default: str = "medium") -> str:
    value = (value or default).lower()
    return value if value in RISK_LEVELS else default


def _clean_req_type(value: str | None, default: str = "technical") -> str:
    value = (value or default).lower()
    return value if value in REQUIREMENT_TYPES else default


def _looks_like_pure_fact(text: str) -> bool:
    prefixes = (
        "项目名称", "招标人", "采购人", "项目预算", "预算", "投资金额",
        "项目编号", "招标编号", "代理机构", "联系方式",
    )
    stripped = text.strip()
    return stripped.startswith(prefixes) and not any(
        marker in stripped for marker in ("必须", "须", "应", "不得", "提供", "提交", "满足", "支持", "完成")
    )


class LLMGateway:
    """OpenAI-compatible chat completions gateway."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout_seconds: int = 60,
        cost_limit_per_project: float = 0.0,
        estimated_cost_per_1k_tokens: float = 0.0,
        model_routing: dict[str, str] | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.cost_limit_per_project = cost_limit_per_project
        self.estimated_cost_per_1k_tokens = estimated_cost_per_1k_tokens
        self.model_routing = model_routing or {}
        self.total_tokens = 0
        self.estimated_cost = 0.0

    async def call(
        self,
        task_type: str,
        messages: list,
        response_schema: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.1,
    ) -> dict:
        if self.cost_limit_per_project and self.estimated_cost >= self.cost_limit_per_project:
            raise RuntimeError("LLM cost limit exceeded for this process")

        selected_model = self.model_routing.get(task_type, self.model)
        await publish_current(
            "llm.request",
            "正在调用模型",
            f"{task_type} · {selected_model}",
            {"task_type": task_type, "model": selected_model},
        )
        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_schema:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"].get("content") or ""
                if not content.strip() and max_tokens < 512:
                    retry_payload = {**payload, "max_tokens": 512}
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=retry_payload,
                    )
                    response.raise_for_status()
                    data = response.json()
        except Exception as exc:
            await publish_current("llm.error", "模型调用失败", str(exc), {"task_type": task_type})
            raise

        usage = data.get("usage") or {}
        total_tokens = int(usage.get("total_tokens") or 0)
        self.total_tokens += total_tokens
        if self.estimated_cost_per_1k_tokens:
            self.estimated_cost += total_tokens / 1000 * self.estimated_cost_per_1k_tokens

        content = data["choices"][0]["message"].get("content") or "{}"
        try:
            parsed = _extract_json_object(content)
        except json.JSONDecodeError:
            if max_tokens >= 1024:
                raise
            retry_payload = {**payload, "max_tokens": 1024}
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=retry_payload,
                )
                response.raise_for_status()
                data = response.json()
            usage = data.get("usage") or {}
            total_tokens = int(usage.get("total_tokens") or 0)
            self.total_tokens += total_tokens
            content = data["choices"][0]["message"].get("content") or "{}"
            parsed = _extract_json_object(content)
        parsed["_llm"] = {
            "task_type": task_type,
            "model": self.model,
            "selected_model": selected_model,
            "usage": usage,
            "estimated_cost": round(self.estimated_cost, 6),
        }
        await publish_current(
            "llm.response",
            "模型已返回结构化结果",
            f"{usage.get('total_tokens', 0)} tokens",
            {"task_type": task_type, "model": selected_model, "usage": usage},
        )
        return parsed


class MockLLMGateway:
    """Mock LLM gateway for local development without credentials."""

    model = "mock-llm"
    total_tokens = 0
    estimated_cost = 0.0

    async def call(
        self,
        task_type: str,
        messages: list,
        response_schema: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.1,
    ) -> dict:
        return {"status": "mock", "task_type": task_type, "message": "Mock LLM response"}


class BaseAgent:
    """Base agent with LLM gateway abstraction and rule-based fallback."""

    def __init__(self, llm_gateway=None):
        self.llm = llm_gateway

    async def call_llm(
        self,
        task_type: str,
        messages: list,
        response_schema: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.1,
    ) -> dict:
        if self.llm:
            await publish_current("agent.step", "准备模型上下文", task_type, {"task_type": task_type})
            return await self.llm.call(task_type, messages, response_schema, max_tokens, temperature)
        return self._mock_response(task_type, messages)

    def _mock_response(self, task_type: str, messages: list) -> dict:
        return {"status": "mock", "task_type": task_type}


class DocumentAgent(BaseAgent):
    """Handles document parsing orchestration."""

    async def parse(self, project_id: str, document_ids: list[str], db_session) -> dict:
        from app.application.document_service import DocumentService

        svc = DocumentService(db_session)
        results = []
        for doc_id in document_ids:
            doc = await svc.parse_document(doc_id)
            results.append({"document_id": doc_id, "status": doc.parse_status, "page_count": doc.page_count})
        return {"parsed_documents": results}


class RequirementAgent(BaseAgent):
    """Extracts requirements, facts, and generates the requirement matrix."""

    async def extract_facts(self, project_id: str, db_session) -> dict:
        from app.application.document_service import DocumentService
        from app.domain.models import ConfirmStatus, ProjectFact, RiskLevel

        svc = DocumentService(db_session)
        docs = await svc.list_documents(project_id)
        all_text = ""
        for doc in docs:
            pages = await svc.get_pages(doc.id)
            for p in pages:
                if p.text:
                    all_text += f"\n[doc:{doc.id} page:{p.page_number}]\n{p.text}\n"

        facts = await self._extract_facts_from_text(all_text, docs)
        for f_data in facts:
            fact = ProjectFact(
                project_id=project_id,
                fact_key=f_data["key"],
                fact_value=f_data["value"],
                source_document_id=f_data.get("source_doc_id", docs[0].id if docs else ""),
                source_page=f_data.get("source_page", 1),
                confidence=f_data.get("confidence", 0.85),
                confirmation_status=ConfirmStatus.PENDING.value,
                risk_level=f_data.get("risk_level", RiskLevel.HIGH.value),
            )
            db_session.add(fact)
        await db_session.flush()
        return {"extracted_facts": len(facts), "facts": facts}

    async def _extract_facts_from_text(self, text: str, docs: list) -> list[dict]:
        if self._has_real_llm() and text.strip():
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是投标文件解析专家。只输出JSON。"
                        "从招标文件中提取关键项目事实，字段为 facts。"
                        "每个fact包含 key,value,source_doc_id,source_page,confidence,risk_level。"
                        "key优先使用 project_name,bidder,budget,duration,deadline,deployment,warranty。"
                    ),
                },
                {"role": "user", "content": _truncate_text(text)},
            ]
            try:
                data = await self.call_llm("extract_project_facts", messages, "json", max_tokens=1600)
                facts = data.get("facts") or []
                normalized = []
                for item in facts[:30]:
                    key = str(item.get("key") or "").strip()
                    value = str(item.get("value") or "").strip()
                    if not key or not value:
                        continue
                    normalized.append({
                        "key": key[:100],
                        "value": value[:1000],
                        "source_doc_id": item.get("source_doc_id") or (docs[0].id if docs else ""),
                        "source_page": int(item.get("source_page") or 1),
                        "confidence": float(item.get("confidence") or 0.8),
                        "risk_level": _clean_risk(item.get("risk_level"), "medium"),
                    })
                if normalized:
                    return normalized
            except Exception:
                pass
        return self._rule_extract_facts_from_text(text, docs)

    def _rule_extract_facts_from_text(self, text: str, docs: list) -> list[dict]:
        facts = []
        patterns = {
            "project_name": [r"项目名称[：:]\s*(.+?)(?:\n|$)", r"项目名称[是为]?\s*(.+?)(?:\n|$)"],
            "bidder": [r"招标人[：:]\s*(.+?)(?:\n|$)", r"招标人[是为]?\s*(.+?)(?:\n|$)"],
            "budget": [r"(?:预算|项目预算|投资金额)[：:是为]?\s*(.+?)(?:\n|$)", r"预算(\d+[\d.]*\s*万?\s*元?)"],
            "duration": [r"(?:工期|建设周期)[：:是为]?\s*(.+?)(?:\n|$)", r"工期(\d+\s*日历天?)"],
            "deadline": [r"(?:投标截止|截止时间|提交截止)[：:是为]?\s*(.+?)(?:\n|$)", r"截止时间[是为]?\s*(\d{4}[年.-]\d{1,2}[月.-]\d{1,2}[日]?\s*\d{1,2}[:：]\d{2})"],
            "deployment": [r"部署方式[：:是为]?\s*(.+?)(?:\n|$)", r"(私有化部署|本地化部署|云部署|混合部署)"],
            "warranty": [r"(?:质保期|维保期)[：:是为]?\s*(.+?)(?:\n|$)", r"(\d+\s*年\s*质保)"],
        }
        for key, pat_list in patterns.items():
            for pattern in pat_list:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if value and len(value) > 1:
                        facts.append({
                            "key": key,
                            "value": value,
                            "source_doc_id": docs[0].id if docs else "",
                            "source_page": 1,
                            "confidence": 0.85,
                            "risk_level": "high" if key in ("deadline", "budget", "bidder") else "medium",
                        })
                        break
        if not any(f["key"] == "project_name" for f in facts):
            facts.append({"key": "project_name", "value": "待提取项目名称", "source_doc_id": docs[0].id if docs else "", "source_page": 1, "confidence": 0.3, "risk_level": "high"})
        return facts

    async def extract_requirements(self, project_id: str, db_session) -> dict:
        from app.application.document_service import DocumentService
        from app.domain.models import Requirement, RequirementStatus, RiskLevel

        svc = DocumentService(db_session)
        docs = await svc.list_documents(project_id)
        all_text = ""
        for doc in docs:
            pages = await svc.get_pages(doc.id)
            for p in pages:
                if p.text:
                    all_text += f"\n[doc:{doc.id} page:{p.page_number}]\n{p.text}\n"

        reqs = await self._extract_requirements_from_text(all_text, docs)
        for r_data in reqs:
            req = Requirement(
                project_id=project_id,
                requirement_text=r_data["text"],
                requirement_type=r_data["type"],
                mandatory=r_data.get("mandatory", False),
                risk_level=r_data.get("risk_level", RiskLevel.MEDIUM.value),
                evidence_required=r_data.get("evidence"),
                source_document_id=r_data.get("source_doc_id", docs[0].id if docs else ""),
                source_page=r_data.get("source_page", 1),
                confidence=r_data.get("confidence", 0.8),
                status=RequirementStatus.PENDING.value,
                subject=r_data.get("subject"),
                action=r_data.get("action"),
                condition=r_data.get("condition"),
                deadline=r_data.get("deadline"),
                penalty=r_data.get("penalty"),
            )
            db_session.add(req)
        await db_session.flush()
        return {"extracted_requirements": len(reqs), "requirements": reqs}

    async def _extract_requirements_from_text(self, text: str, docs: list) -> list[dict]:
        if self._has_real_llm() and text.strip():
            reqs: list[dict] = []
            seen: set[str] = set()
            for chunk in _chunk_text(text):
                messages = [
                    {
                        "role": "system",
                        "content": (
                        "你是投标合规要求抽取专家。只输出JSON。"
                        "返回 requirements 数组。每项包含 text,type,mandatory,risk_level,evidence,"
                        "source_doc_id,source_page,confidence,subject,action,condition,deadline,penalty。"
                        "type只能是 qualification,technical,commercial,scoring,delivery,format。"
                        "risk_level只能是 high,medium,low。"
                        "不要把项目名称、招标人、预算、编号等纯事实抽成要求，除非文本包含投标人必须执行的动作。"
                    ),
                },
                {"role": "user", "content": chunk},
            ]
                try:
                    data = await self.call_llm("extract_requirements", messages, "json", max_tokens=2500)
                except Exception:
                    continue
                for item in (data.get("requirements") or [])[:80]:
                    text_value = str(item.get("text") or item.get("requirement_text") or "").strip()
                    if len(text_value) < 8:
                        continue
                    if _looks_like_pure_fact(text_value):
                        continue
                    dedupe_key = text_value[:120]
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    reqs.append({
                        "text": text_value[:1000],
                        "type": _clean_req_type(item.get("type")),
                        "mandatory": bool(item.get("mandatory")),
                        "risk_level": _clean_risk(item.get("risk_level")),
                        "evidence": item.get("evidence") or item.get("evidence_required"),
                        "source_doc_id": item.get("source_doc_id") or (docs[0].id if docs else ""),
                        "source_page": int(item.get("source_page") or 1),
                        "confidence": float(item.get("confidence") or 0.78),
                        "subject": item.get("subject"),
                        "action": item.get("action"),
                        "condition": item.get("condition"),
                        "deadline": item.get("deadline"),
                        "penalty": item.get("penalty"),
                    })
            if reqs:
                return reqs
        return self._rule_extract_requirements_from_text(text, docs)

    def _rule_extract_requirements_from_text(self, text: str, docs: list) -> list[dict]:
        reqs = []
        high_risk_triggers = ["必须", "不得", "应当", "否决", "无效", "须提供", "废标", "取消资格"]
        mandatory_triggers = ["必须", "须", "应当", "不得", "否决", "废标"]

        lines = text.split("\n")
        for i, line in enumerate(lines):
            line = line.strip()
            if len(line) < 15:
                continue

            risk = "low"
            is_mandatory = any(t in line for t in mandatory_triggers)
            if any(t in line for t in high_risk_triggers):
                risk = "high"
            elif "要求" in line:
                risk = "medium"

            req_type = "technical"
            if any(kw in line for kw in ["资格", "资质", "证书"]):
                req_type = "qualification"
            elif any(kw in line for kw in ["商务", "报价", "价格"]):
                req_type = "commercial"
            elif any(kw in line for kw in ["评分", "分值"]):
                req_type = "scoring"
            elif any(kw in line for kw in ["交付", "提交", "验收"]):
                req_type = "delivery"
            elif any(kw in line for kw in ["格式", "装订", "盖章"]):
                req_type = "format"

            reqs.append({
                "text": line[:500],
                "type": req_type,
                "mandatory": is_mandatory,
                "risk_level": risk,
                "evidence": None,
                "source_doc_id": docs[0].id if docs else "",
                "source_page": i // 30 + 1,
                "confidence": 0.75,
            })
        return reqs

    async def generate_matrix(self, project_id: str, db_session) -> dict:
        from app.domain.models import Requirement
        from sqlalchemy import select

        result = await db_session.execute(
            select(Requirement).where(Requirement.project_id == project_id)
        )
        reqs = result.scalars().all()
        return {"matrix": [{"id": r.id, "text": r.requirement_text[:100], "type": r.requirement_type, "risk": r.risk_level} for r in reqs]}

    def _has_real_llm(self) -> bool:
        return self.llm is not None and not isinstance(self.llm, MockLLMGateway)


class ScoringAgent(BaseAgent):
    """Extracts scoring criteria from tender documents."""

    async def extract_scoring(self, project_id: str, db_session) -> dict:
        from app.application.document_service import DocumentService
        from app.domain.models import ScoringItem

        svc = DocumentService(db_session)
        docs = await svc.list_documents(project_id)
        all_text = ""
        for doc in docs:
            pages = await svc.get_pages(doc.id)
            for p in pages:
                if p.text:
                    all_text += f"\n[doc:{doc.id} page:{p.page_number}]\n{p.text}\n"

        items = await self._extract_scoring_from_text(all_text, docs)
        for item in items:
            si = ScoringItem(
                project_id=project_id,
                title=item["title"],
                score=item.get("score", 0),
                criteria=item.get("criteria"),
                evidence=item.get("evidence"),
                source_document_id=item.get("source_doc_id") or (docs[0].id if docs else ""),
                source_page=item.get("source_page", 1),
                coverage_status="uncovered",
            )
            db_session.add(si)
        await db_session.flush()
        return {"extracted_scoring_items": len(items), "scoring_items": items}

    async def _extract_scoring_from_text(self, text: str, docs: list) -> list[dict]:
        if self._has_real_llm() and text.strip():
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是招标评分表抽取专家。只输出JSON。"
                        "返回 scoring_items 数组。每项包含 title,score,criteria,evidence,source_doc_id,source_page。"
                        "score必须是数字，无法判断时为0。"
                    ),
                },
                {"role": "user", "content": _truncate_text(text, 14000)},
            ]
            try:
                data = await self.call_llm("extract_scoring", messages, "json", max_tokens=2200)
                items = []
                for item in (data.get("scoring_items") or data.get("items") or [])[:80]:
                    title = str(item.get("title") or "").strip()
                    criteria = str(item.get("criteria") or title).strip()
                    if not title and criteria:
                        title = criteria[:120]
                    if not title:
                        continue
                    items.append({
                        "title": title[:255],
                        "score": float(item.get("score") or 0),
                        "criteria": criteria[:1500],
                        "evidence": item.get("evidence"),
                        "source_doc_id": item.get("source_doc_id") or (docs[0].id if docs else ""),
                        "source_page": int(item.get("source_page") or 1),
                    })
                if items:
                    return items
            except Exception:
                pass
        return self._rule_extract_scoring_from_text(text, docs)

    def _rule_extract_scoring_from_text(self, text: str, docs: list) -> list[dict]:
        items = []
        score_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*分", re.IGNORECASE)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            line = line.strip()
            match = score_pattern.search(line)
            if match and len(line) > 10:
                items.append({
                    "title": line[:200],
                    "score": float(match.group(1)),
                    "criteria": line,
                    "source_page": i // 30 + 1,
                })
        return items

    def _has_real_llm(self) -> bool:
        return self.llm is not None and not isinstance(self.llm, MockLLMGateway)


class RetrievalAgent(BaseAgent):
    """Retrieves knowledge from enterprise knowledge base."""

    async def retrieve(self, project_id: str, db_session, section_id: str | None = None) -> dict:
        from app.application.knowledge_service import KnowledgeIndexService
        from app.domain.models import OutlineSection, ProjectFact, Requirement
        from sqlalchemy import select

        query_parts = []
        if section_id:
            section = (await db_session.execute(
                select(OutlineSection).where(OutlineSection.id == section_id)
            )).scalar_one_or_none()
            if section:
                query_parts.append(section.title)

        facts = (await db_session.execute(
            select(ProjectFact).where(ProjectFact.project_id == project_id).limit(20)
        )).scalars().all()
        query_parts.extend(f"{f.fact_key}:{f.fact_value}" for f in facts if f.fact_value)

        reqs = (await db_session.execute(
            select(Requirement).where(Requirement.project_id == project_id).limit(30)
        )).scalars().all()
        query_parts.extend(r.requirement_text for r in reqs if r.requirement_text)

        svc = KnowledgeIndexService(db_session)
        chunks = await svc.retrieve("\n".join(query_parts) or project_id, limit=8, audited_only=True)
        return {"retrieved_chunks": chunks, "query_terms": query_parts[:12]}


class DraftingAgent(BaseAgent):
    """Generates chapter drafts based on requirements, scoring, and knowledge."""

    async def generate_outline(self, project_id: str, db_session) -> dict:
        from app.application.enterprise_service import INDUSTRY_TEMPLATES
        from app.domain.models import OutlineSection, Project, Requirement
        from sqlalchemy import select

        req_result = await db_session.execute(
            select(Requirement).where(Requirement.project_id == project_id)
        )
        reqs = req_result.scalars().all()

        outline_template = [
            ("项目概述与理解", 1, 1),
            ("项目背景", 2, 2),
            ("需求理解", 2, 3),
            ("总体技术方案", 1, 4),
            ("系统总体架构", 2, 5),
            ("技术架构设计", 2, 6),
            ("数据架构设计", 2, 7),
            ("安全方案", 2, 8),
            ("项目实施", 1, 9),
            ("实施计划", 2, 10),
            ("项目组织与人员", 2, 11),
            ("质量保证", 2, 12),
            ("培训与售后服务", 1, 13),
            ("培训方案", 2, 14),
            ("售后服务与技术支持", 2, 15),
            ("公司资质与案例", 1, 16),
            ("公司资质", 2, 17),
            ("同类案例", 2, 18),
        ]
        project = (await db_session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        if project and project.project_type in INDUSTRY_TEMPLATES:
            outline_template = [
                (title, level, idx)
                for idx, (title, level) in enumerate(INDUSTRY_TEMPLATES[project.project_type], start=1)
            ]

        if self._has_real_llm() and reqs:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是资深投标文件大纲规划专家。只输出JSON。"
                        "根据需求生成 outline_sections 数组，每项包含 title,level,sort_order。"
                        "章节应覆盖技术、商务、实施、服务、资质与评分响应。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        [{"text": r.requirement_text, "type": r.requirement_type, "risk": r.risk_level} for r in reqs[:80]],
                        ensure_ascii=False,
                    ),
                },
            ]
            try:
                data = await self.call_llm("generate_outline", messages, "json", max_tokens=1800)
                generated = []
                for i, item in enumerate((data.get("outline_sections") or [])[:40], start=1):
                    title = str(item.get("title") or "").strip()
                    if title:
                        generated.append((title[:255], int(item.get("level") or 1), int(item.get("sort_order") or i)))
                if generated:
                    outline_template = generated
            except Exception:
                pass

        sections = []
        for title, level, order in outline_template:
            s = OutlineSection(
                project_id=project_id,
                title=title,
                level=level,
                sort_order=order,
                status="pending",
            )
            db_session.add(s)
            sections.append(s)
        await db_session.flush()
        return {"outline_sections": len(sections)}

    async def generate_draft(self, project_id: str, section_id: str | None = None, db_session=None) -> dict:
        from app.domain.models import DraftVersion, KnowledgeChunk, OutlineSection, ProjectFact, Requirement
        from sqlalchemy import select

        if section_id:
            section_result = await db_session.execute(
                select(OutlineSection).where(OutlineSection.id == section_id)
            )
            section = section_result.scalar_one_or_none()
        else:
            section_result = await db_session.execute(
                select(OutlineSection).where(OutlineSection.project_id == project_id, OutlineSection.status == "pending").limit(1)
            )
            section = section_result.scalar_one_or_none()

        if not section:
            return {"error": "No section found to generate"}

        facts_result = await db_session.execute(
            select(ProjectFact).where(ProjectFact.project_id == project_id)
        )
        facts = {f.fact_key: f.fact_value for f in facts_result.scalars().all()}

        req_result = await db_session.execute(
            select(Requirement).where(Requirement.project_id == project_id).limit(30)
        )
        requirements = req_result.scalars().all()

        from app.application.knowledge_service import KnowledgeIndexService

        retrieval_query = "\n".join(
            [section.title]
            + [str(v) for v in facts.values()]
            + [r.requirement_text for r in requirements[:20]]
        )
        retrieved = await KnowledgeIndexService(db_session).retrieve(retrieval_query, limit=5, audited_only=True)
        retrieved_ids = [item["id"] for item in retrieved]
        if retrieved_ids:
            chunks_result = await db_session.execute(
                select(KnowledgeChunk).where(KnowledgeChunk.id.in_(retrieved_ids))
            )
            chunk_map = {c.id: c for c in chunks_result.scalars().all()}
            chunks = [chunk_map[cid] for cid in retrieved_ids if cid in chunk_map]
        else:
            chunks = []

        content = await self._generate_section_content(section.title, facts, chunks, requirements)
        citations = self._build_citations(chunks)

        draft = DraftVersion(
            section_id=section.id,
            content=content,
            citations=citations,
            generated_by="drafting_agent",
            model_name=getattr(self.llm, "model", "mock-llm"),
            prompt_version="1.1.0",
            word_count=len(content),
        )
        db_session.add(draft)
        section.status = "drafted"
        section.current_version_id = draft.id
        await db_session.flush()

        return {"section_id": section.id, "draft_id": draft.id, "word_count": len(content), "citations": citations}

    async def _generate_section_content(self, title: str, facts: dict, chunks: list, requirements: list | None = None) -> str:
        if self._has_real_llm():
            context = {
                "section_title": title,
                "project_facts": facts,
                "requirements": [
                    {
                        "text": r.requirement_text,
                        "type": r.requirement_type,
                        "mandatory": r.mandatory,
                        "risk_level": r.risk_level,
                    }
                    for r in (requirements or [])[:30]
                ],
                "knowledge_chunks": [
                    {
                        "id": c.id,
                        "material_name": c.material_name,
                        "source_page": c.source_page,
                        "content": (c.content or "")[:1000],
                    }
                    for c in chunks[:5]
                ],
            }
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是资深中文投标文件撰写专家。只输出JSON。"
                        "输出 {\"content\":\"...\"}。正文使用Markdown，必须紧扣章节标题、项目事实、招标要求和知识库证据。"
                        "对缺少证据的信息使用【待确认】标记，不得编造企业资质或案例。"
                    ),
                },
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ]
            try:
                data = await self.call_llm("generate_section_content", messages, "json", max_tokens=3000, temperature=0.2)
                content = str(data.get("content") or "").strip()
                if len(content) > 50:
                    return content
            except Exception:
                pass
        return self._rule_generate_section_content(title, facts, chunks)

    def _rule_generate_section_content(self, title: str, facts: dict, chunks: list) -> str:
        project_name = facts.get("project_name", "本项目")
        lines = [
            f"## {title}",
            "",
            f"本章节针对{project_name}的{title}相关要求进行详细说明。",
            "",
        ]
        if "技术" in title or "架构" in title:
            lines.append("### 技术架构概述")
            lines.append("")
            lines.append(f"针对{project_name}的实际需求，系统采用分层架构设计，主要包括：")
            lines.append("")
            lines.append("1. **基础设施层**：提供计算、存储和网络资源基础支撑")
            lines.append("2. **数据层**：负责数据存储、处理和分析能力")
            lines.append("3. **服务层**：提供业务逻辑处理和API服务")
            lines.append("4. **应用层**：面向最终用户提供交互界面")
            lines.append("")
            lines.append("【待确认】具体技术选型需根据企业实际产品能力补充。")
        elif "实施" in title:
            lines.append("### 实施计划")
            lines.append("")
            duration = facts.get("duration", "项目周期")
            lines.append(f"根据招标文件要求，{duration}内完成项目建设。实施分为以下阶段：")
            lines.append("")
            lines.append("1. **需求调研与设计阶段**：深入理解需求，完成详细设计")
            lines.append("2. **开发与测试阶段**：按模块开发，并行推进测试")
            lines.append("3. **部署与上线阶段**：完成系统部署和数据迁移")
            lines.append("4. **试运行与验收阶段**：系统试运行并完成最终验收")
            lines.append("")
            lines.append("【待确认】具体时间节点需根据实际工期确认。")
        elif "案例" in title:
            lines.append("### 同类案例")
            lines.append("")
            if chunks:
                for c in chunks[:3]:
                    lines.append(f"- **{c.material_name}**：{c.content[:150] if c.content else '详见附件'}（来源：{c.document_version}，第{c.source_page}页）")
            else:
                lines.append("【缺少材料】请补充企业同类案例材料。")
        elif "培训" in title:
            lines.append("### 培训方案")
            lines.append("")
            lines.append(f"针对{project_name}，提供以下培训服务：")
            lines.append("")
            lines.append("1. **系统管理员培训**：涵盖系统部署、配置、监控和故障排除")
            lines.append("2. **操作人员培训**：面向日常使用人员，覆盖全部功能模块")
            lines.append("3. **开发人员培训**：面向二次开发需求，提供API和扩展开发指导")
            lines.append("")
            lines.append("【待确认】培训人数、时长和地点需根据招标文件确认。")
        else:
            lines.append(f"本部分内容针对{project_name}的{title}要求进行编制。")
            lines.append("")
            lines.append("【待确认】需要更多企业材料支撑以完善本章节内容。")

        if facts.get("deployment"):
            lines.append("")
            lines.append(f"部署方式：{facts['deployment']}")
        if facts.get("warranty"):
            lines.append(f"质保期：{facts['warranty']}")

        return "\n".join(lines)

    def _build_citations(self, chunks: list) -> list:
        return [{
            "chunk_id": c.id,
            "source": c.material_name or "",
            "page": c.source_page,
            "version": c.document_version or "",
            "status": "verified" if c.is_audited else "unverified",
            "snippet": (c.content or "")[:100],
        } for c in chunks]

    def _has_real_llm(self) -> bool:
        return self.llm is not None and not isinstance(self.llm, MockLLMGateway)


class ReviewAgent(BaseAgent):
    """Performs document review for coverage, consistency, and risk."""

    async def review(self, project_id: str, db_session, review_type: str = "full") -> dict:
        from app.application.review_export_service import ReviewService

        svc = ReviewService(db_session)
        review_run = await svc.run_review(project_id, review_type)
        findings = await svc.list_findings(review_run.id)
        return {
            "review_run_id": review_run.id,
            "total_findings": len(findings),
            "high_risk": sum(1 for f in findings if f.risk_level == "high"),
            "medium_risk": sum(1 for f in findings if f.risk_level == "medium"),
        }


def build_llm_gateway():
    runtime = get_runtime_llm_config()
    provider = (runtime.provider or "mock").lower()
    if provider in ("mock", "none", "disabled") or not runtime.api_key:
        return MockLLMGateway()
    default_base_urls = {
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com",
    }
    default_models = {
        "openai": "gpt-4o-mini",
        "deepseek": "deepseek-v4-flash",
    }
    fast_model = runtime.fast_model or default_models.get(provider, "gpt-4o-mini")
    quality_model = runtime.quality_model or ("deepseek-v4-pro" if provider == "deepseek" else "gpt-4o")
    model_routing = {
        "extract_project_facts": fast_model,
        "extract_requirements": fast_model,
        "extract_scoring": fast_model,
        "generate_outline": fast_model,
        "generate_section_content": quality_model,
        "review_document_semantic": quality_model,
        "generate_commercial_bid": quality_model,
        "generate_qualification_bid": quality_model,
        "consultation_answer": quality_model,
        "opportunity_heat_analysis": fast_model,
        **(settings.LLM_MODEL_ROUTING or {}),
    }
    return LLMGateway(
        api_key=runtime.api_key,
        base_url=runtime.base_url or default_base_urls.get(provider, "https://api.openai.com/v1"),
        model=runtime.model or default_models.get(provider, "gpt-4o-mini"),
        timeout_seconds=runtime.timeout_seconds or settings.LLM_TIMEOUT_SECONDS,
        cost_limit_per_project=runtime.cost_limit_per_project or 0.0,
        estimated_cost_per_1k_tokens=runtime.estimated_cost_per_1k_tokens or 0.0,
        model_routing=model_routing,
    )


active_llm_gateway = build_llm_gateway()
document_agent = DocumentAgent(active_llm_gateway)
requirement_agent = RequirementAgent(active_llm_gateway)
scoring_agent = ScoringAgent(active_llm_gateway)
retrieval_agent = RetrievalAgent(active_llm_gateway)
drafting_agent = DraftingAgent(active_llm_gateway)
review_agent = ReviewAgent(active_llm_gateway)


def reload_llm_gateway():
    global active_llm_gateway
    active_llm_gateway = build_llm_gateway()
    for agent in (
        document_agent,
        requirement_agent,
        scoring_agent,
        retrieval_agent,
        drafting_agent,
        review_agent,
    ):
        agent.llm = active_llm_gateway
    try:
        from app.agents.planner_agent import planner_agent

        planner_agent.llm = active_llm_gateway
    except Exception:
        pass
    try:
        from app.agents.specialized_agents import commercial_agent, qualification_agent

        commercial_agent.llm = active_llm_gateway
        qualification_agent.llm = active_llm_gateway
    except Exception:
        pass
    try:
        from app.workflows import workflow_service

        workflow_service.active_llm_gateway = active_llm_gateway
    except Exception:
        pass
    return active_llm_gateway
