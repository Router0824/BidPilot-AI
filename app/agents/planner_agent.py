import json
import uuid
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import BaseAgent, MockLLMGateway, active_llm_gateway
from app.domain.models import (
    ConfirmationTask,
    Document,
    NodeRun,
    Project,
    ProjectFact,
    Requirement,
    ReviewFinding,
    ReviewRun,
    WorkflowRun,
)
from app.workflows.engine import TENDER_WORKFLOW_DEFINITION, get_node_definition


ALLOWED_NODE_IDS = {node.name for node in TENDER_WORKFLOW_DEFINITION["nodes"]}
FIXED_WORKFLOW_NODE_IDS = [node.name for node in TENDER_WORKFLOW_DEFINITION["nodes"]]


class PlannerNodeSelection(BaseModel):
    node_id: str
    reason: str
    priority: int = 100
    requires_human_confirmation: bool = False

    @field_validator("node_id")
    @classmethod
    def node_must_be_registered(cls, value: str) -> str:
        if value not in ALLOWED_NODE_IDS:
            raise ValueError(f"unregistered node: {value}")
        return value


class PlannerSkippedNode(BaseModel):
    node_id: str
    reason: str

    @field_validator("node_id")
    @classmethod
    def node_must_be_registered(cls, value: str) -> str:
        if value not in ALLOWED_NODE_IDS:
            raise ValueError(f"unregistered node: {value}")
        return value


class PlannerDependency(BaseModel):
    from_node: str = Field(alias="from")
    to: str

    @field_validator("from_node", "to")
    @classmethod
    def node_must_be_registered(cls, value: str) -> str:
        if value not in ALLOWED_NODE_IDS:
            raise ValueError(f"unregistered node: {value}")
        return value


class PlannerPlan(BaseModel):
    plan_id: str
    goal: str
    selected_nodes: list[PlannerNodeSelection]
    skipped_nodes: list[PlannerSkippedNode] = []
    dependencies: list[PlannerDependency] = []
    human_confirmation_required: bool = False
    confirmation_reason: str | None = None
    expected_outputs: list[str] = []
    risk_level: Literal["low", "medium", "high"] = "medium"

    @field_validator("selected_nodes")
    @classmethod
    def selected_nodes_must_not_be_empty(cls, value: list[PlannerNodeSelection]) -> list[PlannerNodeSelection]:
        if not value:
            raise ValueError("selected_nodes cannot be empty")
        seen = set()
        deduped = []
        for item in sorted(value, key=lambda node: node.priority):
            if item.node_id not in seen:
                seen.add(item.node_id)
                deduped.append(item)
        return deduped


class PlannerDecision(BaseModel):
    plan: PlannerPlan
    input_context: dict
    fallback_used: bool = False
    fallback_reason: str | None = None
    raw_output: dict | None = None


class PlannerAgent(BaseAgent):
    async def plan(
        self,
        project_id: str,
        db_session: AsyncSession,
        document_ids: list[str] | None = None,
    ) -> PlannerDecision:
        context = await self._collect_context(project_id, db_session, document_ids or [])
        try:
            raw = await self._call_or_mock(context)
            plan = PlannerPlan.model_validate(raw)
            plan = self._normalize_plan_order(plan)
            return PlannerDecision(plan=plan, input_context=context, raw_output=raw)
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return PlannerDecision(
                plan=self._fallback_plan(str(exc)),
                input_context=context,
                fallback_used=True,
                fallback_reason=str(exc),
            )

    async def _call_or_mock(self, context: dict) -> dict:
        if self._has_real_llm():
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是投标 AI Agent 的工作流 Planner。只输出 JSON，不要输出解释文本。"
                        "只能选择已注册节点，不能发明节点。"
                        f"可选节点白名单：{', '.join(FIXED_WORKFLOW_NODE_IDS)}。"
                        "字段必须包含 plan_id, goal, selected_nodes, skipped_nodes, dependencies,"
                        "human_confirmation_required, confirmation_reason, expected_outputs, risk_level。"
                    ),
                },
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ]
            data = await self.call_llm("plan_workflow", messages, "json", max_tokens=1800, temperature=0.1)
            return data
        return self._mock_plan(context).model_dump(by_alias=True)

    async def _collect_context(self, project_id: str, db_session: AsyncSession, document_ids: list[str]) -> dict:
        project = (await db_session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        docs = (await db_session.execute(select(Document).where(Document.project_id == project_id))).scalars().all()
        run = (await db_session.execute(
            select(WorkflowRun).where(WorkflowRun.project_id == project_id).order_by(WorkflowRun.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        node_runs: list[NodeRun] = []
        if run:
            node_runs = list((await db_session.execute(
                select(NodeRun).where(NodeRun.workflow_run_id == run.id).order_by(NodeRun.created_at)
            )).scalars().all())
        facts = (await db_session.execute(select(ProjectFact).where(ProjectFact.project_id == project_id))).scalars().all()
        reqs = (await db_session.execute(select(Requirement).where(Requirement.project_id == project_id))).scalars().all()
        confirmations = (await db_session.execute(
            select(ConfirmationTask).where(ConfirmationTask.project_id == project_id)
        )).scalars().all()
        review_runs = (await db_session.execute(
            select(ReviewRun).where(ReviewRun.project_id == project_id).order_by(ReviewRun.created_at.desc()).limit(3)
        )).scalars().all()
        review_findings = []
        if review_runs:
            review_findings = list((await db_session.execute(
                select(ReviewFinding).where(ReviewFinding.review_run_id.in_([r.id for r in review_runs]))
            )).scalars().all())

        return {
            "project": {
                "id": project.id if project else project_id,
                "name": project.name if project else "",
                "project_type": project.project_type if project else "",
                "workflow_status": project.workflow_status if project else "",
            },
            "requested_document_ids": document_ids,
            "documents": [
                {
                    "id": d.id,
                    "name": d.name,
                    "document_type": d.document_type,
                    "parse_status": d.parse_status,
                    "page_count": d.page_count,
                    "file_hash": d.file_hash,
                }
                for d in docs
            ],
            "has_addendum": any(d.document_type == "addendum" for d in docs),
            "completed_nodes": [n.node_name for n in node_runs if n.status == "succeeded"],
            "node_results": [
                {
                    "node_id": n.node_name,
                    "status": n.status,
                    "retry_count": n.retry_count,
                    "error_message": n.error_message,
                    "output_summary": self._summarize_output(n.output_snapshot),
                }
                for n in node_runs[-20:]
            ],
            "human_confirmation": [
                {
                    "task_id": c.id,
                    "task_type": c.task_type,
                    "status": c.status,
                    "risk_level": c.risk_level,
                    "created_node": c.created_node,
                }
                for c in confirmations
            ],
            "facts": [
                {
                    "key": f.fact_key,
                    "value": f.fact_value,
                    "risk_level": f.risk_level,
                    "confirmation_status": f.confirmation_status,
                }
                for f in facts
            ],
            "risk_items": [
                {
                    "requirement_id": r.id,
                    "type": r.requirement_type,
                    "risk_level": r.risk_level,
                    "mandatory": r.mandatory,
                    "status": r.status,
                    "text": r.requirement_text[:200],
                }
                for r in reqs
                if r.risk_level == "high" or r.mandatory
            ],
            "reviewer_output": [
                {
                    "issue_id": f.id,
                    "issue_type": f.finding_type,
                    "risk_level": f.risk_level,
                    "description": f.description,
                    "status": f.status,
                }
                for f in review_findings
            ],
            "workflow_errors": [
                {"node_id": n.node_name, "error": n.error_message}
                for n in node_runs
                if n.status == "failed" and n.error_message
            ],
            "registered_nodes": FIXED_WORKFLOW_NODE_IDS,
        }

    def _mock_plan(self, context: dict) -> PlannerPlan:
        completed = set(context.get("completed_nodes") or [])
        docs = context.get("documents") or []
        has_addendum = bool(context.get("has_addendum"))
        pending_parse = any(d.get("parse_status") != "completed" for d in docs)
        has_requirements = bool(context.get("risk_items"))
        has_pending_confirmation = any(
            item.get("status") == "pending" and item.get("risk_level") == "high"
            for item in context.get("human_confirmation") or []
        )

        reasons = {
            "parse_documents": "检测到待处理文件，需要先解析文档内容" if pending_parse else "文档解析结果仍可复用",
            "extract_project_facts": "需要从招标文件和补遗中提取项目关键事实",
            "detect_addendum_conflicts": "检测到补遗文件，需要识别其对既有事实和结果的影响",
            "extract_requirements": "需要提取资格、技术、商务、交付和格式要求",
            "extract_scoring": "需要抽取评分项用于后续响应矩阵",
            "generate_matrix": "需要生成要求矩阵，支撑后续章节覆盖检查",
            "generate_outline": "需要根据要求生成投标文件大纲",
            "retrieve_knowledge": "需要检索企业材料作为生成依据",
            "generate_draft": "需要生成或更新投标章节草稿",
            "review_document": "需要审查缺失响应、引用和一致性风险",
            "ready_to_export": "前序结果完成后进入导出准备状态",
        }

        selected = []
        if pending_parse or not docs:
            selected.append("parse_documents")
        if "extract_project_facts" not in completed or has_addendum:
            selected.append("extract_project_facts")
        if has_addendum:
            selected.append("detect_addendum_conflicts")
        if not has_requirements or "extract_requirements" not in completed:
            selected.append("extract_requirements")
        for node_id in [
            "extract_scoring",
            "generate_matrix",
            "generate_outline",
            "retrieve_knowledge",
            "generate_draft",
            "review_document",
            "ready_to_export",
        ]:
            if node_id not in completed:
                selected.append(node_id)

        if not selected:
            selected = FIXED_WORKFLOW_NODE_IDS.copy()

        selected_nodes = [
            PlannerNodeSelection(
                node_id=node_id,
                reason=reasons[node_id],
                priority=idx + 1,
                requires_human_confirmation=bool(get_node_definition(node_id).human_gate),
            )
            for idx, node_id in enumerate(selected)
        ]
        skipped_nodes = [
            PlannerSkippedNode(node_id=node_id, reason=reasons.get(node_id, "已有有效结果，本轮跳过"))
            for node_id in FIXED_WORKFLOW_NODE_IDS
            if node_id not in selected
        ]
        dependencies = [
            PlannerDependency(**{"from": selected[idx], "to": selected[idx + 1]})
            for idx in range(len(selected) - 1)
        ]
        return PlannerPlan(
            plan_id=str(uuid.uuid4()),
            goal="生成完整且可追溯的投标技术文件",
            selected_nodes=selected_nodes,
            skipped_nodes=skipped_nodes,
            dependencies=dependencies,
            human_confirmation_required=has_pending_confirmation or has_addendum,
            confirmation_reason="检测到补遗文件或高风险确认项，需要人工确认后继续" if (has_pending_confirmation or has_addendum) else None,
            expected_outputs=["结构化要求", "执行记录", "投标章节草稿", "审查结果"],
            risk_level="high" if has_pending_confirmation or has_addendum else "medium",
        )

    def _fallback_plan(self, reason: str) -> PlannerPlan:
        selected_nodes = [
            PlannerNodeSelection(
                node_id=node_id,
                reason=f"Planner 输出不可用，使用固定安全工作流 fallback：{reason}",
                priority=idx + 1,
                requires_human_confirmation=bool(get_node_definition(node_id).human_gate),
            )
            for idx, node_id in enumerate(FIXED_WORKFLOW_NODE_IDS)
        ]
        dependencies = [
            PlannerDependency(**{"from": FIXED_WORKFLOW_NODE_IDS[idx], "to": FIXED_WORKFLOW_NODE_IDS[idx + 1]})
            for idx in range(len(FIXED_WORKFLOW_NODE_IDS) - 1)
        ]
        return PlannerPlan(
            plan_id=str(uuid.uuid4()),
            goal="生成完整且可追溯的投标技术文件",
            selected_nodes=selected_nodes,
            skipped_nodes=[],
            dependencies=dependencies,
            human_confirmation_required=False,
            confirmation_reason=None,
            expected_outputs=["固定工作流输出"],
            risk_level="medium",
        )

    def _normalize_plan_order(self, plan: PlannerPlan) -> PlannerPlan:
        node_order = {node_id: idx for idx, node_id in enumerate(FIXED_WORKFLOW_NODE_IDS)}
        sorted_nodes = sorted(plan.selected_nodes, key=lambda item: node_order[item.node_id])
        selected_ids = [node.node_id for node in sorted_nodes]
        plan.selected_nodes = [
            PlannerNodeSelection(
                node_id=node.node_id,
                reason=node.reason,
                priority=idx + 1,
                requires_human_confirmation=bool(get_node_definition(node.node_id).human_gate),
            )
            for idx, node in enumerate(sorted_nodes)
        ]
        plan.dependencies = [
            PlannerDependency(**{"from": selected_ids[idx], "to": selected_ids[idx + 1]})
            for idx in range(len(selected_ids) - 1)
        ]
        return plan

    def _summarize_output(self, output: dict | None) -> dict:
        if not output:
            return {}
        summary = {}
        for key, value in output.items():
            if isinstance(value, list):
                summary[key] = len(value)
            elif isinstance(value, dict):
                summary[key] = list(value.keys())[:8]
            else:
                summary[key] = value
        return summary

    def _has_real_llm(self) -> bool:
        return self.llm is not None and not isinstance(self.llm, MockLLMGateway)


planner_agent = PlannerAgent(active_llm_gateway)
