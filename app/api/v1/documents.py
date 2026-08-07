from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import require_auth
from app.application.document_service import DocumentService
from app.application.enterprise_service import EnterpriseService
from app.core.config import settings
from app.schemas import APIResponse

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])


@router.get("")
async def list_documents(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = DocumentService(db)
    docs = await svc.list_documents(project_id)
    return APIResponse(data=[{
        "id": d.id, "project_id": d.project_id, "name": d.name,
        "document_type": d.document_type, "version": d.version,
        "file_size": d.file_size, "parse_status": d.parse_status,
        "page_count": d.page_count, "is_latest": d.is_latest,
        "priority": d.priority, "uploaded_by": d.uploaded_by,
        "created_at": str(d.created_at),
    } for d in docs])


@router.post("")
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    document_type: str = Form(default="tender_main"),
    version: str = Form(default="1"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, "文件过大，请使用分片上传")
    content = await file.read()
    svc = DocumentService(db)
    doc = await svc.upload_document(project_id, file.filename, content, document_type, user)
    await EnterpriseService(db).audit("document", project_id, "upload", user, None, {"document_id": doc.id, "name": doc.name, "type": doc.document_type})
    return APIResponse(data={
        "id": doc.id, "name": doc.name, "document_type": doc.document_type,
        "file_size": doc.file_size, "parse_status": doc.parse_status,
    })


@router.post("/upload-sessions")
async def create_upload_session(
    project_id: str,
    filename: str = Form(...),
    total_size: int = Form(...),
    file_hash: str = Form(...),
    document_type: str = Form(default="tender_main"),
    chunk_size: int = Form(default=8 * 1024 * 1024),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = DocumentService(db)
    session = await svc.create_upload_session(project_id, filename, total_size, file_hash, document_type, user, chunk_size)
    return APIResponse(data={
        "upload_session_id": session["id"],
        "chunk_size": session["chunk_size"],
        "received_chunks": session["received_chunks"],
    })


@router.put("/upload-sessions/{upload_session_id}/chunks")
async def upload_chunk(
    project_id: str,
    upload_session_id: str,
    chunk_index: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    content = await file.read()
    svc = DocumentService(db)
    try:
        result = await svc.upload_chunk(project_id, upload_session_id, chunk_index, content)
        return APIResponse(data=result)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/upload-sessions/{upload_session_id}/complete")
async def complete_upload_session(
    project_id: str,
    upload_session_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = DocumentService(db)
    try:
        doc = await svc.complete_upload_session(project_id, upload_session_id, user)
        await EnterpriseService(db).audit("document", project_id, "chunked_upload_complete", user, None, {"document_id": doc.id, "name": doc.name})
        return APIResponse(data={
            "id": doc.id,
            "name": doc.name,
            "document_type": doc.document_type,
            "file_size": doc.file_size,
            "file_hash": doc.file_hash,
            "parse_status": doc.parse_status,
        })
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{document_id}/parse")
async def parse_document(
    project_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = DocumentService(db)
    try:
        doc = await svc.parse_document(document_id)
        return APIResponse(data={
            "document_id": doc.id, "parse_status": doc.parse_status,
            "page_count": doc.page_count,
        })
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/{document_id}/pages")
async def get_pages(
    project_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = DocumentService(db)
    pages = await svc.get_pages(document_id)
    return APIResponse(data=[{
        "id": p.id, "document_id": p.document_id, "page_number": p.page_number,
        "text": p.text[:500] if p.text else None, "parse_method": p.parse_method,
        "ocr_confidence": p.ocr_confidence, "table_count": p.table_count,
    } for p in pages])


@router.delete("/{document_id}")
async def delete_document(
    project_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = DocumentService(db)
    ok = await svc.delete_document(document_id)
    if not ok:
        raise HTTPException(404, "文件不存在")
    await EnterpriseService(db).audit("document", project_id, "delete", user, {"document_id": document_id})
    return APIResponse(data={"deleted": True})
