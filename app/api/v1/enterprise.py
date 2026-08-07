import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.specialized_agents import commercial_agent, qualification_agent
from app.application.enterprise_service import EnterpriseService
from app.core.auth import MOCK_USERS, require_auth, require_role
from app.core.config import settings
from app.core.database import async_session, get_db
from app.observability.progress import progress_context, publish_progress
from app.realtime.collaboration import collaboration_hub
from app.schemas import APIResponse

router = APIRouter(prefix="/projects/{project_id}/enterprise", tags=["enterprise"])


def user_from_token(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return MOCK_USERS.get(payload.get("sub"))
    except JWTError:
        return None


@router.websocket("/collaboration/ws")
async def collaboration_ws(project_id: str, websocket: WebSocket, token: str | None = None):
    user = user_from_token(token)
    if not user:
        await websocket.close(code=4401)
        return
    await collaboration_hub.connect(project_id, websocket, user)
    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            message.update({
                "project_id": project_id,
                "user_id": user["id"],
                "display_name": user.get("display_name", user["username"]),
            })
            await collaboration_hub.broadcast(project_id, message)
    except WebSocketDisconnect:
        await collaboration_hub.disconnect(project_id, websocket, user)


@router.get("/members")
async def list_members(project_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)):
    svc = EnterpriseService(db)
    members = await svc.list_members(project_id)
    return APIResponse(data=[{
        "id": m.id, "user_id": m.user_id, "user_name": m.user_name,
        "role": m.role, "access_level": m.access_level, "created_at": str(m.created_at),
    } for m in members])


@router.post("/members")
async def upsert_member(
    project_id: str,
    user_id: str,
    role: str = "writer",
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin", "project_admin")),
):
    svc = EnterpriseService(db)
    member = await svc.upsert_member(project_id, user_id, role, user)
    return APIResponse(data={"id": member.id, "user_id": member.user_id, "role": member.role})


@router.post("/sections/{section_id}/assign")
async def assign_section(
    project_id: str,
    section_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin", "project_admin")),
):
    svc = EnterpriseService(db)
    section = await svc.assign_section(section_id, user_id, user)
    if not section:
        raise HTTPException(404, "章节不存在")
    await publish_progress(project_id, "assignment.changed", "章节已分配", f"{section.title} → {section.owner_name}", "assignment")
    return APIResponse(data={"section_id": section.id, "owner_id": section.owner_id, "owner_name": section.owner_name})


@router.post("/sections/{section_id}/lock")
async def lock_section(
    project_id: str,
    section_id: str,
    client_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    result = await EnterpriseService(db).acquire_lock(section_id, user, client_id)
    if "error" in result:
        raise HTTPException(409 if result["error"] == "locked" else 403, result)
    return APIResponse(data=result)


@router.delete("/sections/{section_id}/lock")
async def unlock_section(
    project_id: str,
    section_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    ok = await EnterpriseService(db).release_lock(section_id, user)
    return APIResponse(data={"released": ok})


@router.post("/sections/{section_id}/approval")
async def submit_approval(
    project_id: str,
    section_id: str,
    reviewer_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    approval = await EnterpriseService(db).submit_section_approval(section_id, reviewer_id, user)
    if not approval:
        raise HTTPException(404, "章节不存在")
    return APIResponse(data={"approval_id": approval.id, "status": approval.status})


@router.post("/approvals/{approval_id}/resolve")
async def resolve_approval(
    project_id: str,
    approval_id: str,
    action: str,
    comment: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin", "project_admin", "reviewer")),
):
    if action not in ("approve", "reject"):
        raise HTTPException(400, "action must be approve or reject")
    approval = await EnterpriseService(db).resolve_approval(approval_id, action, comment, user)
    if not approval:
        raise HTTPException(404, "审批不存在")
    return APIResponse(data={"approval_id": approval.id, "status": approval.status})


@router.get("/approvals")
async def list_approvals(project_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)):
    approvals = await EnterpriseService(db).list_approvals(project_id)
    return APIResponse(data=[{
        "id": a.id, "section_id": a.section_id, "draft_version_id": a.draft_version_id,
        "submitted_by": a.submitted_by, "reviewer_id": a.reviewer_id,
        "reviewer_name": a.reviewer_name, "status": a.status,
        "comment": a.comment, "created_at": str(a.created_at),
        "resolved_at": str(a.resolved_at) if a.resolved_at else None,
    } for a in approvals])


@router.get("/templates")
async def list_templates(project_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)):
    return APIResponse(data=await EnterpriseService(db).list_templates())


@router.post("/templates/{template_key}/apply")
async def apply_template(
    project_id: str,
    template_key: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin", "project_admin")),
):
    result = await EnterpriseService(db).apply_template(project_id, template_key, user)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return APIResponse(data=result)


@router.get("/audits")
async def list_audits(
    project_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin", "project_admin", "reviewer")),
):
    logs = await EnterpriseService(db).list_audits(project_id, limit)
    return APIResponse(data=[{
        "id": log.id, "resource_type": log.resource_type, "resource_id": log.resource_id,
        "action": log.action, "operator": log.operator,
        "before_value": log.before_value, "after_value": log.after_value,
        "reason": log.reason, "created_at": str(log.created_at),
    } for log in logs])


@router.post("/commercial/generate")
async def generate_commercial(project_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)):
    await publish_progress(project_id, "node.start", "开始生成商务标", None, "generate_commercial_bid")
    with progress_context(project_id, "generate_commercial_bid"):
        result = await commercial_agent.generate(project_id, db)
    await EnterpriseService(db).audit("commercial_bid", project_id, "generate", user, None, {"agent": result["agent"]})
    await publish_progress(project_id, "node.done", "商务标生成完成", None, "generate_commercial_bid")
    return APIResponse(data=result)


@router.post("/qualification/generate")
async def generate_qualification(project_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)):
    await publish_progress(project_id, "node.start", "开始生成资格标", None, "generate_qualification_bid")
    with progress_context(project_id, "generate_qualification_bid"):
        result = await qualification_agent.generate(project_id, db)
    await EnterpriseService(db).audit("qualification_bid", project_id, "generate", user, None, {"agent": result["agent"]})
    await publish_progress(project_id, "node.done", "资格标生成完成", None, "generate_qualification_bid")
    return APIResponse(data=result)
