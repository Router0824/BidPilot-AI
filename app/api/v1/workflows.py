import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import JWTError, jwt
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import MOCK_USERS, require_auth
from app.core.config import settings
from app.observability.progress import subscribe, unsubscribe
from app.workflows.workflow_service import WorkflowService
from app.schemas import (
    APIResponse,
    WorkflowStartRequest,
    ConfirmationAction,
    WorkflowImpactPreviewRequest,
    WorkflowIncrementalRunRequest,
)

router = APIRouter(prefix="/projects/{project_id}/workflow", tags=["workflow"])


def _validate_stream_token(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        return MOCK_USERS.get(username)
    except JWTError:
        return None


@router.get("")
async def get_workflow_status(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = WorkflowService(db)
    status = await svc.get_workflow_status(project_id)
    return APIResponse(data=status)


@router.get("/stream")
async def stream_workflow_status(
    project_id: str,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if not _validate_stream_token(token):
        raise HTTPException(401, "未登录或令牌已过期")

    async def event_generator():
        queue = subscribe(project_id)
        last_payload = None
        try:
            while not await request.is_disconnected():
                svc = WorkflowService(db)
                status = await svc.get_workflow_status(project_id)
                payload = json.dumps(status, ensure_ascii=False, default=str)
                if payload != last_payload:
                    yield {"event": "workflow.status.changed", "data": payload}
                    last_payload = payload

                try:
                    progress = await asyncio.wait_for(queue.get(), timeout=2)
                    yield {"event": "agent.progress", "data": json.dumps(progress, ensure_ascii=False, default=str)}
                except asyncio.TimeoutError:
                    pass
        finally:
            unsubscribe(project_id, queue)

    return EventSourceResponse(event_generator())


@router.post("/start")
async def start_workflow(
    project_id: str,
    data: WorkflowStartRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = WorkflowService(db)
    doc_ids = data.document_ids if data else []
    try:
        wf_run = await svc.start_workflow(project_id, doc_ids, user)
        return APIResponse(data={
            "workflow_run_id": wf_run.id,
            "status": wf_run.status,
            "current_node": wf_run.current_node,
        })
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/impact-preview")
async def preview_workflow_impact(
    project_id: str,
    data: WorkflowImpactPreviewRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = WorkflowService(db)
    result = await svc.create_impact_preview(
        project_id,
        data.change_type,
        data.changed_document_ids,
        user,
    )
    return APIResponse(data=result)


@router.post("/incremental-rerun")
async def start_incremental_rerun(
    project_id: str,
    data: WorkflowIncrementalRunRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = WorkflowService(db)
    try:
        wf_run = await svc.start_incremental_workflow(
            project_id=project_id,
            change_type=data.change_type,
            changed_document_ids=data.changed_document_ids,
            confirm_high_risk=data.confirm_high_risk,
            user=user,
            preview_id=data.preview_id,
        )
        return APIResponse(data={
            "workflow_run_id": wf_run.id,
            "status": wf_run.status,
            "current_node": wf_run.current_node,
        })
    except PermissionError as e:
        raise HTTPException(409, {"confirmation_required": True, "reason": str(e)})
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/pause")
async def pause_workflow(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = WorkflowService(db)
    result = await svc.pause_workflow(project_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return APIResponse(data=result)


@router.post("/resume")
async def resume_workflow(
    project_id: str,
    from_node: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = WorkflowService(db)
    result = await svc.resume_workflow(project_id, from_node)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return APIResponse(data=result)


@router.post("/retry")
async def retry_node(
    project_id: str,
    node_name: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = WorkflowService(db)
    result = await svc.retry_node(project_id, node_name)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return APIResponse(data=result)


@router.post("/cancel")
async def cancel_workflow(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = WorkflowService(db)
    result = await svc.cancel_workflow(project_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return APIResponse(data=result)


# ── Confirmations ──
@router.get("/confirmations")
async def list_confirmations(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = WorkflowService(db)
    tasks = await svc.list_confirmation_tasks(project_id)
    return APIResponse(data=[{
        "id": t.id, "project_id": t.project_id, "task_type": t.task_type,
        "resource_type": t.resource_type, "resource_id": t.resource_id,
        "candidate_value": t.candidate_value, "source_document_id": t.source_document_id,
        "source_page": t.source_page, "risk_level": t.risk_level,
        "conflicts": t.conflicts, "status": t.status, "assigned_to": t.assigned_to,
        "created_at": str(t.created_at),
    } for t in tasks])


@router.post("/confirmations/{confirmation_id}/resolve")
async def resolve_confirmation(
    project_id: str,
    confirmation_id: str,
    data: ConfirmationAction,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = WorkflowService(db)
    result = await svc.process_confirmation(
        project_id, confirmation_id, data.action, data.value, data.comment, user
    )
    if "error" in result:
        raise HTTPException(404, result["error"])
    return APIResponse(data=result)
