from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.consultation_service import ConsultationService
from app.core.auth import require_auth
from app.core.database import get_db
from app.schemas import APIResponse


router = APIRouter(prefix="/projects/{project_id}/consultation", tags=["consultation"])


class CreateSessionRequest(BaseModel):
    title: str | None = None


class AskRequest(BaseModel):
    question: str


@router.get("/sessions")
async def list_sessions(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = ConsultationService(db)
    sessions = await svc.list_sessions(project_id)
    return APIResponse(data=[svc._session_dict(session) for session in sessions])


@router.post("/sessions")
async def create_session(
    project_id: str,
    data: CreateSessionRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = ConsultationService(db)
    session = await svc.create_session(project_id, user, data.title if data else None)
    return APIResponse(data=svc._session_dict(session))


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    project_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = ConsultationService(db)
    if not await svc._get_session(project_id, session_id):
        raise HTTPException(404, "咨询会话不存在")
    messages = await svc.list_messages(session_id)
    return APIResponse(data=[svc._message_dict(msg) for msg in messages])


@router.post("/sessions/{session_id}/ask")
async def ask(
    project_id: str,
    session_id: str,
    data: AskRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    if not data.question.strip():
        raise HTTPException(400, "问题不能为空")
    svc = ConsultationService(db)
    try:
        return APIResponse(data=await svc.ask(project_id, session_id, data.question, user))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
