import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.domain.models import (
    WorkflowRun, NodeRun, Project, ConfirmationTask,
    NodeStatus, ConfirmStatus, WorkflowPlan, WorkflowImpactPreview
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
from app.agents.planner_agent import FIXED_WORKFLOW_NODE_IDS, planner_agent
from app.core.config import settings
from app.observability.progress import progress_context, publish_progress
from app.workflows.dependency_graph import WorkflowImpactService


class NodeCostLimitExceeded(RuntimeError):
    pass


class NodeManualRequired(RuntimeError):
    pass


_running_node_keys: set[tuple[str, str]] = set()


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
        latest_plan = await self.get_latest_plan(project_id)
        if not run:
            project = (await self.db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
            return {
                "has_active_workflow": False,
                "workflow_status": project.workflow_status if project else "created",
                "current_node": None,
                "planner_plan": self._serialize_plan(latest_plan) if latest_plan else None,
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
            "planner_plan": self._serialize_plan(latest_plan) if latest_plan else None,
            "node_runs": [
                {
                    "id": nr.id, "node_name": nr.node_name, "agent_name": nr.agent_name,
                    "status": nr.status, "model_name": nr.model_name,
                    "token_usage": nr.token_usage, "latency_ms": nr.latency_ms,
                    "retry_count": nr.retry_count, "error_message": nr.error_message,
                    "error_code": nr.error_code,
                    "execution": (nr.output_snapshot or {}).get("_execution") if isinstance(nr.output_snapshot, dict) else None,
                    "started_at": nr.started_at, "completed_at": nr.completed_at,
                } for nr in node_runs
            ],
        }

    async def start_workflow(self, project_id: str, document_ids: list[str], user: dict) -> WorkflowRun:
        existing = await self.get_workflow_run(project_id)
        if existing and existing.status not in (NodeStatus.FAILED.value, NodeStatus.CANCELLED.value, NodeStatus.SUCCEEDED.value):
            raise ValueError("项目已有运行中的工作流")

        project = (await self.db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        if not project:
            raise ValueError("项目不存在")

        wf_run = WorkflowRun(
            project_id=project_id,
            definition_key="tender_mvp",
            definition_version="1.0.0",
            status=NodeStatus.RUNNING.value,
            current_node=None,
        )
        self.db.add(wf_run)
        project.workflow_status = ProjectWorkflowStatus.PARSING.value
        await self.db.flush()

        decision = await planner_agent.plan(project_id, self.db, document_ids)
        selected_nodes = [item.node_id for item in decision.plan.selected_nodes]
        if not selected_nodes:
            selected_nodes = FIXED_WORKFLOW_NODE_IDS.copy()

        wf_run.current_node = selected_nodes[0]
        plan_record = WorkflowPlan(
            project_id=project_id,
            workflow_run_id=wf_run.id,
            plan_id=decision.plan.plan_id,
            goal=decision.plan.goal,
            selected_nodes=[item.model_dump() for item in decision.plan.selected_nodes],
            skipped_nodes=[item.model_dump() for item in decision.plan.skipped_nodes],
            dependencies=[item.model_dump(by_alias=True) for item in decision.plan.dependencies],
            expected_outputs=decision.plan.expected_outputs,
            human_confirmation_required=decision.plan.human_confirmation_required,
            confirmation_reason=decision.plan.confirmation_reason,
            risk_level=decision.plan.risk_level,
            input_context=decision.input_context,
            fallback_used=decision.fallback_used,
            fallback_reason=decision.fallback_reason,
            raw_output=decision.raw_output,
        )
        self.db.add(plan_record)
        await self.db.flush()
        await publish_progress(
            project_id,
            "planner.done",
            "Planner 已生成执行计划",
            f"执行 {len(selected_nodes)} 个节点，跳过 {len(decision.plan.skipped_nodes)} 个节点",
            "planner_agent",
            {
                "plan_id": decision.plan.plan_id,
                "risk_level": decision.plan.risk_level,
                "fallback_used": decision.fallback_used,
                "selected_nodes": selected_nodes,
            },
        )

        await self._execute_planned_node(wf_run, selected_nodes, 0, project_id, document_ids)
        return wf_run

    async def get_latest_plan(self, project_id: str, workflow_run_id: str | None = None) -> WorkflowPlan | None:
        query = select(WorkflowPlan).where(WorkflowPlan.project_id == project_id)
        if workflow_run_id:
            query = query.where(WorkflowPlan.workflow_run_id == workflow_run_id)
        result = await self.db.execute(query.order_by(WorkflowPlan.created_at.desc()).limit(1))
        return result.scalar_one_or_none()

    async def create_impact_preview(
        self,
        project_id: str,
        change_type: str = "documents_changed",
        changed_document_ids: list[str] | None = None,
        user: dict | None = None,
    ) -> dict:
        impact = await WorkflowImpactService(self.db).preview(project_id, change_type, changed_document_ids or [])
        preview = WorkflowImpactPreview(
            project_id=project_id,
            change_type=change_type,
            changed_resources=impact["changed_resources"],
            changed_signals=impact["changed_signals"],
            affected_nodes=impact["affected_nodes"],
            unaffected_nodes=impact["unaffected_nodes"],
            dependency_edges=impact["dependency_edges"],
            high_risk=impact["high_risk"],
            confirmation_required=impact["confirmation_required"],
            confirmation_reason=impact["confirmation_reason"],
            created_by=user["id"] if user else "system",
        )
        self.db.add(preview)
        await self.db.flush()
        return self._serialize_impact_preview(preview)

    async def get_impact_preview(self, preview_id: str) -> WorkflowImpactPreview | None:
        result = await self.db.execute(select(WorkflowImpactPreview).where(WorkflowImpactPreview.id == preview_id))
        return result.scalar_one_or_none()

    def _serialize_impact_preview(self, preview: WorkflowImpactPreview) -> dict:
        return {
            "id": preview.id,
            "project_id": preview.project_id,
            "change_type": preview.change_type,
            "changed_resources": preview.changed_resources or [],
            "changed_signals": preview.changed_signals or [],
            "affected_nodes": preview.affected_nodes or [],
            "unaffected_nodes": preview.unaffected_nodes or [],
            "dependency_edges": preview.dependency_edges or [],
            "high_risk": preview.high_risk,
            "confirmation_required": preview.confirmation_required,
            "confirmation_reason": preview.confirmation_reason,
            "created_by": preview.created_by,
            "created_at": str(preview.created_at) if preview.created_at else None,
            "executed_at": str(preview.executed_at) if preview.executed_at else None,
        }

    async def start_incremental_workflow(
        self,
        project_id: str,
        change_type: str,
        changed_document_ids: list[str],
        confirm_high_risk: bool,
        user: dict,
        preview_id: str | None = None,
    ) -> WorkflowRun:
        existing = await self.get_workflow_run(project_id)
        if existing and existing.status not in (NodeStatus.FAILED.value, NodeStatus.CANCELLED.value, NodeStatus.SUCCEEDED.value):
            raise ValueError("项目已有运行中的工作流")

        preview = await self.get_impact_preview(preview_id) if preview_id else None
        if not preview:
            preview_data = await self.create_impact_preview(project_id, change_type, changed_document_ids, user)
            preview = await self.get_impact_preview(preview_data["id"])
        if not preview:
            raise ValueError("无法创建影响预览")

        if preview.confirmation_required and not confirm_high_risk:
            raise PermissionError(preview.confirmation_reason or "本次变更需要人工确认")

        affected_nodes = preview.affected_nodes or []
        selected_nodes = [item["node_id"] for item in affected_nodes]
        if not selected_nodes:
            raise ValueError("没有需要重新执行的节点")

        project = (await self.db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        if not project:
            raise ValueError("项目不存在")

        import datetime
        wf_run = WorkflowRun(
            project_id=project_id,
            definition_key="tender_incremental",
            definition_version="1.0.0",
            status=NodeStatus.RUNNING.value,
            current_node=selected_nodes[0],
        )
        self.db.add(wf_run)
        project.workflow_status = ProjectWorkflowStatus.RETRYING.value
        preview.executed_at = datetime.datetime.now(datetime.timezone.utc)
        await self.db.flush()

        plan_record = WorkflowPlan(
            project_id=project_id,
            workflow_run_id=wf_run.id,
            plan_id=f"incremental-{preview.id}",
            goal="只重新执行受本次变更影响的工作流节点",
            selected_nodes=[
                {
                    "node_id": item["node_id"],
                    "reason": item["reason"],
                    "priority": idx + 1,
                    "requires_human_confirmation": item.get("requires_human_confirmation", False),
                }
                for idx, item in enumerate(affected_nodes)
            ],
            skipped_nodes=[
                {"node_id": item["node_id"], "reason": item["reason"]}
                for item in (preview.unaffected_nodes or [])
            ],
            dependencies=preview.dependency_edges or [],
            expected_outputs=["增量重执行结果", "保留未受影响历史结果"],
            human_confirmation_required=preview.confirmation_required,
            confirmation_reason=preview.confirmation_reason,
            risk_level="high" if preview.high_risk else "medium",
            input_context={
                "preview_id": preview.id,
                "change_type": preview.change_type,
                "changed_resources": preview.changed_resources,
                "changed_signals": preview.changed_signals,
            },
            fallback_used=False,
            raw_output=self._serialize_impact_preview(preview),
            created_by="dependency_graph",
        )
        self.db.add(plan_record)
        await self.db.flush()
        await publish_progress(
            project_id,
            "impact.confirmed",
            "已确认增量重执行计划",
            f"重新执行 {len(selected_nodes)} 个节点，保留 {len(preview.unaffected_nodes or [])} 个节点结果",
            "dependency_graph",
            {"preview_id": preview.id, "selected_nodes": selected_nodes},
        )

        await self._execute_planned_node(wf_run, selected_nodes, 0, project_id, changed_document_ids)
        return wf_run

    def _serialize_plan(self, plan: WorkflowPlan | None) -> dict | None:
        if not plan:
            return None
        return {
            "id": plan.id,
            "plan_id": plan.plan_id,
            "workflow_run_id": plan.workflow_run_id,
            "goal": plan.goal,
            "selected_nodes": plan.selected_nodes or [],
            "skipped_nodes": plan.skipped_nodes or [],
            "dependencies": plan.dependencies or [],
            "expected_outputs": plan.expected_outputs or [],
            "human_confirmation_required": plan.human_confirmation_required,
            "confirmation_reason": plan.confirmation_reason,
            "risk_level": plan.risk_level,
            "fallback_used": plan.fallback_used,
            "fallback_reason": plan.fallback_reason,
            "created_by": plan.created_by,
            "created_at": plan.created_at,
        }

    async def _execute_planned_node(
        self,
        wf_run: WorkflowRun,
        node_sequence: list[str],
        index: int,
        project_id: str,
        extra: dict | list | None = None,
    ) -> NodeRun | None:
        if index >= len(node_sequence):
            import datetime
            wf_run.status = NodeStatus.SUCCEEDED.value
            wf_run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            await publish_progress(project_id, "workflow.done", "工作流执行完成", "Planner 计划内节点已全部完成")
            await self.db.flush()
            return None
        return await self._execute_node(wf_run, node_sequence[index], project_id, extra, node_sequence, index)

    def _estimate_total_cost(self, total_tokens: int) -> float:
        return (
            total_tokens / 1000 * settings.LLM_ESTIMATED_COST_PER_1K_TOKENS
            if settings.LLM_ESTIMATED_COST_PER_1K_TOKENS else 0.0
        )

    def _configured_cost_limit(self, node_def) -> float:
        if node_def and node_def.cost_limit:
            return float(node_def.cost_limit)
        return float(settings.LLM_COST_LIMIT_PER_PROJECT or 0.0)

    def _classify_error(self, exc: Exception) -> tuple[str, bool, bool]:
        if isinstance(exc, asyncio.TimeoutError):
            return "timeout", True, False
        if isinstance(exc, NodeCostLimitExceeded):
            return "cost_limit_exceeded", False, True
        if isinstance(exc, NodeManualRequired):
            return "manual_required", False, True
        if isinstance(exc, ValueError):
            return "validation_error", False, False
        return "runtime_error", True, False

    def _retry_delay(self, node_def, retry_index: int) -> int:
        backoff = list(node_def.retry_backoff_seconds or []) if node_def else []
        if retry_index < len(backoff):
            return int(backoff[retry_index])
        base = backoff[-1] if backoff else 5
        return int(base * (2 ** max(0, retry_index - len(backoff) + 1)))

    async def _execute_node(self, wf_run: WorkflowRun, node_name: str, project_id: str,
                             extra: dict | list | None = None,
                             node_sequence: list[str] | None = None,
                             sequence_index: int = 0) -> NodeRun:
        node_def = get_node_definition(node_name)
        import datetime
        import time
        if not node_def:
            raise ValueError(f"未注册的工作流节点：{node_name}")

        running_key = (wf_run.id, node_name)
        if running_key in _running_node_keys:
            raise ValueError(f"节点正在执行，已阻止重复并发：{node_name}")

        existing_success = (await self.db.execute(
            select(NodeRun).where(
                NodeRun.workflow_run_id == wf_run.id,
                NodeRun.node_name == node_name,
                NodeRun.status.in_([NodeStatus.SUCCEEDED.value, NodeStatus.WAITING_CONFIRMATION.value]),
            ).order_by(NodeRun.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if existing_success:
            await publish_progress(
                project_id,
                "node.idempotent",
                "节点结果已存在，复用本次工作流内结果",
                node_name,
                node_name,
                {"node_run_id": existing_success.id, "idempotency_key": node_def.idempotency_key},
            )
            if node_sequence and sequence_index + 1 < len(node_sequence):
                await self._execute_planned_node(wf_run, node_sequence, sequence_index + 1, project_id, existing_success.output_snapshot)
            return existing_success

        _running_node_keys.add(running_key)
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
            retry_delays: list[int] = []
            total_delay_seconds = 0
            output = None
            max_attempts = max(1, int(node_def.max_retries or 0) + 1)
            for attempt in range(1, max_attempts + 1):
                current_total_tokens = int(getattr(active_llm_gateway, "total_tokens", 0) or 0)
                current_cost = self._estimate_total_cost(current_total_tokens)
                cost_limit = self._configured_cost_limit(node_def)
                if cost_limit and current_cost >= cost_limit:
                    raise NodeCostLimitExceeded(f"达到成本上限 {cost_limit}，当前估算成本 {round(current_cost, 6)}")

                node_run.retry_count = attempt - 1
                await self.db.flush()
                await publish_progress(
                    project_id,
                    "node.start" if attempt == 1 else "node.retry.start",
                    "开始执行节点" if attempt == 1 else "开始重试节点",
                    node_name,
                    node_name,
                    {
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "timeout_seconds": node_def.timeout_seconds,
                        "idempotency_key": node_def.idempotency_key,
                    },
                )
                try:
                    with progress_context(project_id, node_name):
                        output = await asyncio.wait_for(
                            self._dispatch_node(node_name, project_id, extra),
                            timeout=node_def.timeout_seconds,
                        )
                    break
                except Exception as attempt_exc:
                    error_code, retryable, manual_required = self._classify_error(attempt_exc)
                    if not retryable or attempt >= max_attempts:
                        if manual_required:
                            node_run.status = NodeStatus.MANUAL_REQUIRED.value
                            wf_run.status = NodeStatus.WAITING_CONFIRMATION.value
                            await publish_progress(
                                project_id,
                                "node.waiting_confirmation",
                                "节点需要人工确认",
                                str(attempt_exc),
                                node_name,
                                {"error_code": error_code, "attempt": attempt},
                            )
                        raise attempt_exc
                    delay = self._retry_delay(node_def, attempt - 1)
                    retry_delays.append(delay)
                    total_delay_seconds += delay
                    node_run.status = NodeStatus.RETRY_SCHEDULED.value
                    wf_run.status = NodeStatus.RETRY_SCHEDULED.value
                    node_run.error_code = error_code
                    node_run.error_message = str(attempt_exc)
                    await self.db.flush()
                    await publish_progress(
                        project_id,
                        "node.retry",
                        "节点执行失败，准备重试",
                        str(attempt_exc),
                        node_name,
                        {
                            "error_code": error_code,
                            "attempt": attempt,
                            "next_attempt": attempt + 1,
                            "delay_seconds": delay,
                            "total_delay_seconds": total_delay_seconds,
                        },
                    )
                    await asyncio.sleep(delay)
                    node_run.status = NodeStatus.RUNNING.value
                    wf_run.status = NodeStatus.RUNNING.value

            if output is None:
                output = {}
            token_delta = max(0, int(getattr(active_llm_gateway, "total_tokens", 0) or 0) - tokens_before)
            estimated_cost = self._estimate_total_cost(token_delta)
            output_meta = {
                "_execution": {
                    "attempts": node_run.retry_count + 1,
                    "retry_delays_seconds": retry_delays,
                    "total_retry_delay_seconds": total_delay_seconds,
                    "timeout_seconds": node_def.timeout_seconds,
                    "idempotency_key": node_def.idempotency_key,
                    "token_usage": token_delta,
                    "estimated_cost": round(estimated_cost, 6),
                }
            }
            output = {**output, **output_meta} if isinstance(output, dict) else {"result": output, **output_meta}
            node_run.output_snapshot = output
            node_run.status = NodeStatus.SUCCEEDED.value
            node_run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            node_run.latency_ms = int((time.monotonic() - started_monotonic) * 1000)
            node_run.token_usage = token_delta
            node_run.error_code = None
            node_run.error_message = None
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
                await publish_progress(
                    project_id,
                    "node.waiting_confirmation",
                    "节点等待人工确认",
                    node_name,
                    node_name,
                    {"risk_level": node_def.risk_level, "requires_human_confirmation": True},
                )
            else:
                next_node = (
                    node_sequence[sequence_index + 1]
                    if node_sequence and sequence_index + 1 < len(node_sequence)
                    else get_next_node(node_name, success=True)
                )
                if next_node:
                    wf_run.status = NodeStatus.RUNNING.value
                    await self.db.flush()
                    if node_sequence:
                        await self._execute_planned_node(wf_run, node_sequence, sequence_index + 1, project_id, output)
                    else:
                        await self._execute_node(wf_run, next_node, project_id, output)
                else:
                    wf_run.status = NodeStatus.SUCCEEDED.value
                    wf_run.completed_at = datetime.datetime.now(datetime.timezone.utc)

        except Exception as e:
            error_code, _, manual_required = self._classify_error(e)
            if not manual_required:
                node_run.status = NodeStatus.FAILED.value
                wf_run.status = NodeStatus.FAILED.value
            else:
                node_run.status = NodeStatus.MANUAL_REQUIRED.value
                wf_run.status = NodeStatus.WAITING_CONFIRMATION.value
            node_run.error_message = str(e)
            node_run.error_code = error_code
            node_run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            node_run.latency_ms = int((time.monotonic() - started_monotonic) * 1000)
            node_run.token_usage = max(0, int(getattr(active_llm_gateway, "total_tokens", 0) or 0) - tokens_before)
            wf_run.error_message = str(e)
            node_run.output_snapshot = {
                "_execution": {
                    "attempts": node_run.retry_count + 1,
                    "error_code": error_code,
                    "token_usage": node_run.token_usage,
                    "estimated_cost": round(self._estimate_total_cost(node_run.token_usage), 6),
                }
            }
            await publish_progress(
                project_id,
                "node.failed" if not manual_required else "node.waiting_confirmation",
                "节点执行失败" if not manual_required else "节点等待人工处理",
                str(e),
                node_name,
                {"error_code": error_code, "retry_count": node_run.retry_count},
            )
        finally:
            _running_node_keys.discard(running_key)

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
            plan = await self.get_latest_plan(project_id, run.id)
            sequence = [item.get("node_id") for item in (plan.selected_nodes or [])] if plan else []
            if sequence and run.current_node in sequence:
                next_index = sequence.index(run.current_node) + 1
                next_node = sequence[next_index] if next_index < len(sequence) else None
            else:
                next_node = get_next_node(run.current_node, success=True) if run.current_node else None
            if next_node:
                if sequence and next_node in sequence:
                    await self._execute_planned_node(run, sequence, sequence.index(next_node), project_id)
                else:
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

        plan = await self.get_latest_plan(project_id, run.id)
        sequence = [item.get("node_id") for item in (plan.selected_nodes or [])] if plan else []
        if sequence and run.current_node in sequence:
            next_index = sequence.index(run.current_node) + 1
            next_node = sequence[next_index] if next_index < len(sequence) else None
        else:
            next_node = get_next_node(run.current_node, success=True) if run.current_node else None
        if next_node:
            run.status = NodeStatus.RUNNING.value
            await self.db.flush()
            if sequence and next_node in sequence:
                await self._execute_planned_node(run, sequence, sequence.index(next_node), project_id)
            else:
                await self._execute_node(run, next_node, project_id)
        else:
            run.status = NodeStatus.SUCCEEDED.value
            await self.db.flush()

    async def list_confirmation_tasks(self, project_id: str) -> list[ConfirmationTask]:
        result = await self.db.execute(
            select(ConfirmationTask).where(ConfirmationTask.project_id == project_id).order_by(ConfirmationTask.created_at.desc())
        )
        return list(result.scalars().all())
