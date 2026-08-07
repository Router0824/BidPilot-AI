from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Document, NodeRun, WorkflowRun
from app.workflows.engine import TENDER_WORKFLOW_DEFINITION, get_node_definition


ChangeType = Literal["documents_changed", "addendum_uploaded", "manual_confirmation_changed", "reviewer_issues_changed"]


NODE_ORDER = [node.name for node in TENDER_WORKFLOW_DEFINITION["nodes"]]


def _node_index(node_name: str) -> int:
    try:
        return NODE_ORDER.index(node_name)
    except ValueError:
        return len(NODE_ORDER)


class WorkflowDependencyGraph:
    def __init__(self) -> None:
        self.nodes = {node.name: node for node in TENDER_WORKFLOW_DEFINITION["nodes"]}

    def node_metadata(self) -> list[dict]:
        return [asdict(self.nodes[name]) for name in NODE_ORDER]

    def signals_for_change(self, change_type: ChangeType, documents: list[Document]) -> list[str]:
        signals: set[str] = set()
        has_unparsed_docs = any(d.parse_status != "completed" for d in documents)
        if change_type == "documents_changed" or has_unparsed_docs:
            signals.add("document_added")
            signals.add("document_pages")
        if change_type == "addendum_uploaded" or any(d.document_type == "addendum" for d in documents):
            signals.add("addendum_document")
            signals.add("project_facts")
            signals.add("requirements")
        if any(d.parse_status != "completed" for d in documents):
            signals.add("uploaded_documents")
        if change_type == "manual_confirmation_changed":
            signals.add("manual_confirmation")
            signals.add("manual_fact_confirmation")
            signals.add("project_facts")
        if change_type == "reviewer_issues_changed":
            signals.add("review_findings")
            signals.add("draft_versions")
        return sorted(signals)

    def calculate_impact(self, changed_signals: list[str], completed_nodes: set[str]) -> dict:
        affected: dict[str, dict] = {}
        changed = set(changed_signals)

        for node_name in NODE_ORDER:
            node = self.nodes[node_name]
            direct_hits = sorted(changed.intersection(node.invalidated_by))
            dependency_hits = [
                dep for dep in node.dependencies
                if dep in affected
            ]
            if direct_hits or dependency_hits:
                reasons = []
                if direct_hits:
                    reasons.append(f"输入信号变化：{', '.join(direct_hits)}")
                if dependency_hits:
                    reasons.append(f"上游节点失效：{', '.join(dependency_hits)}")
                affected[node_name] = {
                    "node_id": node_name,
                    "reason": "；".join(reasons),
                    "priority": _node_index(node_name) + 1,
                    "risk_level": node.risk_level,
                    "requires_human_confirmation": node.requires_human_confirmation,
                    "idempotency_key": node.idempotency_key,
                    "inputs": node.inputs,
                    "outputs": node.outputs,
                    "dependencies": node.dependencies,
                    "historical_result": "will_replace" if node_name in completed_nodes else "not_completed_before",
                }

        affected_ids = set(affected)
        unaffected = []
        for node_name in NODE_ORDER:
            if node_name in affected_ids:
                continue
            node = self.nodes[node_name]
            unaffected.append({
                "node_id": node_name,
                "reason": "未命中本次变化信号，且无受影响上游节点",
                "historical_result": "preserved" if node_name in completed_nodes else "not_available",
                "risk_level": node.risk_level,
            })

        edges = []
        for node_name in affected_ids:
            node = self.nodes[node_name]
            for dep in node.dependencies:
                if dep in affected_ids:
                    edges.append({"from": dep, "to": node_name})

        ordered_affected = sorted(affected.values(), key=lambda item: item["priority"])
        return {
            "affected_nodes": ordered_affected,
            "unaffected_nodes": unaffected,
            "dependency_edges": sorted(edges, key=lambda item: (_node_index(item["from"]), _node_index(item["to"]))),
            "high_risk": any(item["risk_level"] == "high" for item in ordered_affected),
            "confirmation_required": any(
                item["risk_level"] == "high" or item["requires_human_confirmation"]
                for item in ordered_affected
            ),
        }


class WorkflowImpactService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.graph = WorkflowDependencyGraph()

    async def preview(
        self,
        project_id: str,
        change_type: ChangeType = "documents_changed",
        changed_document_ids: list[str] | None = None,
    ) -> dict:
        docs = await self._load_documents(project_id, changed_document_ids or [])
        latest_run = await self._latest_run(project_id)
        completed_nodes = await self._completed_nodes(latest_run.id) if latest_run else set()
        changed_signals = self.graph.signals_for_change(change_type, docs)
        impact = self.graph.calculate_impact(changed_signals, completed_nodes)
        confirmation_reason = None
        if impact["confirmation_required"]:
            high_nodes = [n["node_id"] for n in impact["affected_nodes"] if n["risk_level"] == "high"]
            confirmation_reason = (
                f"本次变更影响高风险节点：{', '.join(high_nodes)}"
                if high_nodes else "本次变更影响需要人工确认的节点"
            )
        return {
            "project_id": project_id,
            "change_type": change_type,
            "changed_resources": [
                {"document_id": d.id, "name": d.name, "document_type": d.document_type, "parse_status": d.parse_status}
                for d in docs
            ],
            "changed_signals": changed_signals,
            "affected_nodes": impact["affected_nodes"],
            "unaffected_nodes": impact["unaffected_nodes"],
            "dependency_edges": impact["dependency_edges"],
            "high_risk": impact["high_risk"],
            "confirmation_required": impact["confirmation_required"],
            "confirmation_reason": confirmation_reason,
        }

    async def _load_documents(self, project_id: str, changed_document_ids: list[str]) -> list[Document]:
        query = select(Document).where(Document.project_id == project_id)
        if changed_document_ids:
            query = query.where(Document.id.in_(changed_document_ids))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _latest_run(self, project_id: str) -> WorkflowRun | None:
        result = await self.db.execute(
            select(WorkflowRun).where(WorkflowRun.project_id == project_id).order_by(WorkflowRun.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def _completed_nodes(self, workflow_run_id: str) -> set[str]:
        result = await self.db.execute(
            select(NodeRun).where(NodeRun.workflow_run_id == workflow_run_id, NodeRun.status == "succeeded")
        )
        return {node.node_name for node in result.scalars().all()}
