from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.domain.models import (
    WorkflowRun, NodeRun, Project, ConfirmationTask,
    NodeStatus, WorkflowStatus as WfStatus, ConfirmStatus
)
from app.workflows.engine import (
    TENDER_WORKFLOW_DEFINITION, get_node_definition, get_next_node,
    get_status_for_node, ProjectWorkflowStatus, WorkflowNodeStatus,
)
from app.agents import (
    active_llm_gateway,
    document_agent, requirement_agent, scoring_agent,
    retrieval_agent, drafting_agent, review_agent,
)
from app.agents.addendum_agent import addendum_agent
from app.core.config import settings
from app.observability.progress import progress_context, publish_progress


class WorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_workflow_run(self, project_id: str) -> WorkflowRun | None:
        result = await self.db.execute(
            select(WorkflowRun).where(
                and_(WorkflowRun.project_id == project_id, WorkflowRun.status.in_([
                    NodeStatus.PENDING.value, NodeStatus.QUEUED.value, NodeStatus.RUNNING.value,
                    NodeStatus.WAITING_CONFIRMATION.value, NodeStatus.FAILED.value,
                    NodeStatus.RETRY_SCHEDULED.value, NodeStatus.SUCCEEDED.value,
                ]))
            ).order_by(WorkflowRun.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_workflow_status(self, project_id: str) -> dict:
        run = await self.get_workflow_run(project_id)
        if not run:
            project = (await self.db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
            return {
                "has_active_workflow": False,
                "workflow_status": project.workflow_status if project else "created",
                "current_node": None,
                "node_runs": [],
            }
        node_runs_result = await self.db.execute(
            select(NodeRun).where(NodeRun.workflow_run_id == run.id).order_by(NodeRun.created_at)
        )
        node_runs = node_runs_result.scalars().all()
        total_tokens = sum(nr.token_usage or 0 for nr in node_runs)
        estimated_cost = (
            total_tokens / 1000 * settings.LLM_ESTIMATED_COST_PER_1K_TOKENS
            if settings.LLM_ESTIMATED_COST_PER_1K_TOKENS else 0.0
        )
        return {
            "has_active_workflow": True,
            "workflow_run_id": run.id,
            "workflow_status": run.status,
            "current_node": run.current_node,
            "definition_key": run.definition_key,
            "definition_version": run.definition_version,
            "token_usage_total": total_tokens,
            "estimated_cost": round(estimated_cost, 6),
            "node_runs": [
                {
                    "id": nr.id, "node_name": nr.node_name, "agent_name": nr.agent_name,
                    "status": nr.status, "model_name": nr.model_name,
                    "token_usage": nr.token_usage, "latency_ms": nr.latency_ms,
                    "retry_count": nr.retry_count, "error_message": nr.error_message,
                    "started_at": nr.started_at, "completed_at": nr.completed_at,
                } for nr in node_runs
            ],
        }

    async def start_workflow(self, project_id: str, document_ids: list[str], user: dict) -> WorkflowRun:
        existing = await self.get_workflow_run(project_id)
        if existing and existing.status not in (NodeStatus.FAILED.value, NodeStatus.CANCELLED.value):
            raise ValueError("项目已有运行中的工作流")

        project = (await self.db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        if not project:
            raise ValueError("项目不存在")

        wf_run = WorkflowRun(
            project_id=project_id,
            definition_key="tender_mvp",
            definition_version="1.0.0",
            status=NodeStatus.RUNNING.value,
            current_node="parse_documents",
        )
        self.db.add(wf_run)
        project.workflow_status = ProjectWorkflowStatus.PARSING.value
        await self.db.flush()

        await self._execute_node(wf_run, "parse_documents", project_id, document_ids)
        return wf_run

    async def _execute_node(self, wf_run: WorkflowRun, node_name: str, project_id: str,
                             extra: dict | list | None = None) -> NodeRun:
        node_def = get_node_definition(node_name)
        import datetime
        import time
        wf_run.status = NodeStatus.RUNNING.value
        started_monotonic = time.monotonic()
        tokens_before = int(getattr(active_llm_gateway, "total_tokens", 0) or 0)
        node_run = NodeRun(
            workflow_run_id=wf_run.id,
            node_name=node_name,
            agent_name=node_def.executor if node_def else "",
            status=NodeStatus.RUNNING.value,
            started_at=datetime.datetime.now(datetime.timezone.utc),
            model_name=getattr(active_llm_gateway, "model", None),
            prompt_version="1.1.0",
        )
        self.db.add(node_run)
        wf_run.current_node = node_name
        await self.db.flush()

        try:
            await publish_progress(project_id, "node.start", "开始执行节点", node_name, node_name)
            with progress_context(project_id, node_name):
                output = await self._dispatch_node(node_name, project_id, extra)
            node_run.output_snapshot = output
            node_run.status = NodeStatus.SUCCEEDED.value
            node_run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            node_run.latency_ms = int((time.monotonic() - started_monotonic) * 1000)
            node_run.token_usage = max(0, int(getattr(active_llm_gateway, "total_tokens", 0) or 0) - tokens_before)
            await publish_progress(
                project_id,
                "node.done",
                "节点执行完成",
                node_name,
                node_name,
                {"latency_ms": node_run.latency_ms, "token_usage": node_run.token_usage},
            )

            project_status = get_status_for_node(node_name)
            project = (await self.db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
            if project:
                project.workflow_status = project_status.value

            if node_def and node_def.human_gate:
                node_run.status = NodeStatus.WAITING_CONFIRMATION.value
                wf_run.status = NodeStatus.WAITING_CONFIRMATION.value
            else:
                next_node = get_next_node(node_name, success=True)
                if next_node:
                    wf_run.status = NodeStatus.RUNNING.value
                    await self.db.flush()
                    await self._execute_node(wf_run, next_node, project_id, output)
                else:
                    wf_run.status = NodeStatus.SUCCEEDED.value
                    wf_run.completed_at = datetime.datetime.now(datetime.timezone.utc)

        except Exception as e:
            node_run.status = NodeStatus.FAILED.value
            node_run.error_message = str(e)
            node_run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            node_run.latency_ms = int((time.monotonic() - started_monotonic) * 1000)
            node_run.token_usage = max(0, int(getattr(active_llm_gateway, "total_tokens", 0) or 0) - tokens_before)
            wf_run.status = NodeStatus.FAILED.value
            wf_run.error_message = str(e)
            await publish_progress(project_id, "node.error", "节点执行失败", str(e), node_name)

        await self.db.flush()
        return node_run

    async def _dispatch_node(self, node_name: str, project_id: str, extra) -> dict:
        if node_name == "parse_documents":
            doc_ids = extra if isinstance(extra, list) else []
            return await document_agent.parse(project_id, doc_ids, self.db)
        elif node_name == "extract_project_facts":
            return await requirement_agent.extract_facts(project_id, self.db)
        elif node_name == "detect_addendum_conflicts":
            return await addendum_agent.detect_conflicts(project_id, self.db)
        elif node_name == "extract_requirements":
            return await requirement_agent.extract_requirements(project_id, self.db)
        elif node_name == "extract_scoring":
            return await scoring_agent.extract_scoring(project_id, self.db)
        elif node_name == "generate_matrix":
            return await requirement_agent.generate_matrix(project_id, self.db)
        elif node_name == "generate_outline":
            return await drafting_agent.generate_outline(project_id, self.db)
        elif node_name == "retrieve_knowledge":
            return await retrieval_agent.retrieve(project_id, self.db)
        elif node_name == "generate_draft":
            return await drafting_agent.generate_draft(project_id, None, self.db)
        elif node_name == "review_document":
            return await review_agent.review(project_id, self.db)
        elif node_name == "ready_to_export":
            return {"status": "ready"}
        return {"status": "unknown_node"}

    async def pause_workflow(self, project_id: str) -> dict:
        run = await self.get_workflow_run(project_id)
        if not run:
            return {"error": "No active workflow"}
        run.status = NodeStatus.WAITING_CONFIRMATION.value
        await self.db.flush()
        return {"status": "paused"}

    async def resume_workflow(self, project_id: str, from_node: str | None = None) -> dict:
        run = await self.get_workflow_run(project_id)
        if not run:
            return {"error": "No active workflow"}

        run.status = NodeStatus.RUNNING.value
        if from_node:
            await self._execute_node(run, from_node, project_id)
        else:
            next_node = get_next_node(run.current_node, success=True) if run.current_node else None
            if next_node:
                await self._execute_node(run, next_node, project_id)
            else:
                run.status = NodeStatus.SUCCEEDED.value
                await self.db.flush()
        return {"status": "resumed"}

    async def retry_node(self, project_id: str, node_name: str) -> dict:
        run = await self.get_workflow_run(project_id)
        if not run:
            return {"error": "No active workflow"}
        run.status = NodeStatus.RETRY_SCHEDULED.value
        await self.db.flush()
        await self._execute_node(run, node_name, project_id)
        return {"status": "retrying"}

    async def cancel_workflow(self, project_id: str) -> dict:
        run = await self.get_workflow_run(project_id)
        if not run:
            return {"error": "No active workflow"}
        run.status = NodeStatus.CANCELLED.value
        project = (await self.db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        if project:
            project.workflow_status = ProjectWorkflowStatus.CANCELLED.value
        await self.db.flush()
        return {"status": "cancelled"}

    async def process_confirmation(self, project_id: str, confirmation_id: str, action: str,
                                    value: str | None = None, comment: str | None = None,
                                    user: dict | None = None) -> dict:
        result = await self.db.execute(
            select(ConfirmationTask).where(ConfirmationTask.id == confirmation_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return {"error": "Confirmation task not found"}

        task.status = action if action != "modify_and_approve" else "approved_modified"
        task.resolved_by = user["id"] if user else "system"
        task.resolved_value = {"value": value} if value else task.candidate_value
        task.comment = comment
        import datetime
        task.resolved_at = datetime.datetime.now(datetime.timezone.utc)

        if action in ("approve", "modify_and_approve"):
            if task.resource_type == "project_fact" and task.resource_id:
                from app.domain.models import ProjectFact
                fact_result = await self.db.execute(
                    select(ProjectFact).where(ProjectFact.id == task.resource_id)
                )
                fact = fact_result.scalar_one_or_none()
                if fact:
                    fact.confirmation_status = ConfirmStatus.CONFIRMED.value
                    fact.confirmed_by = user["id"] if user else "system"
                    if value:
                        fact.fact_value = value

        await self._resume_after_confirmation(project_id)
        await self.db.flush()
        return {"status": "confirmed", "task_id": confirmation_id}

    async def _resume_after_confirmation(self, project_id: str) -> None:
        run = await self.get_workflow_run(project_id)
        if not run or run.status != NodeStatus.WAITING_CONFIRMATION.value:
            return

        from app.domain.models import ConfirmationTask
        pending_result = await self.db.execute(
            select(ConfirmationTask).where(
                and_(ConfirmationTask.project_id == project_id, ConfirmationTask.status == "pending")
            )
        )
        if pending_result.scalars().first():
            return

        next_node = get_next_node(run.current_node, success=True) if run.current_node else None
        if next_node:
            run.status = NodeStatus.RUNNING.value
            await self.db.flush()
            await self._execute_node(run, next_node, project_id)
        else:
            run.status = NodeStatus.SUCCEEDED.value
            await self.db.flush()

    async def list_confirmation_tasks(self, project_id: str) -> list[ConfirmationTask]:
        result = await self.db.execute(
            select(ConfirmationTask).where(ConfirmationTask.project_id == project_id).order_by(ConfirmationTask.created_at.desc())
        )
        return list(result.scalars().all())
