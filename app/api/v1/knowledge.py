from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import require_auth, require_role
from app.domain.models import KnowledgeChunk
from app.application.knowledge_service import KnowledgeIndexService, embed_text
from app.schemas import APIResponse

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("")
async def list_knowledge(
    material_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    q = select(KnowledgeChunk)
    if material_type:
        q = q.where(KnowledgeChunk.material_type == material_type)
    q = q.order_by(KnowledgeChunk.updated_at.desc()).limit(50)
    result = await db.execute(q)
    chunks = result.scalars().all()
    return APIResponse(data=[{
        "id": c.id, "material_name": c.material_name, "material_type": c.material_type,
        "product_line": c.product_line, "content": (c.content or "")[:200],
        "document_version": c.document_version, "source_page": c.source_page,
        "is_audited": c.is_audited, "is_expired": c.is_expired,
        "access_level": c.access_level, "has_embedding": bool(c.embedding),
        "title_path": c.title_path, "created_at": str(c.created_at),
    } for c in chunks])


@router.post("")
async def add_knowledge(
    material_name: str = Form(...),
    material_type: str = Form("company_product"),
    content: str = Form(...),
    product_line: str = Form(""),
    source_page: int = Form(1),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin", "project_admin")),
):
    svc = KnowledgeIndexService(db)
    chunks = await svc.add_material(material_name, material_type, content, product_line, source_page, audited=False)
    return APIResponse(data={
        "id": chunks[0].id if chunks else None,
        "material_name": material_name,
        "chunk_count": len(chunks),
        "status": "created",
    })


@router.post("/rebuild-index")
async def rebuild_knowledge_index(
    material_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin", "project_admin")),
):
    svc = KnowledgeIndexService(db)
    return APIResponse(data=await svc.rebuild_index(material_type))


@router.get("/search")
async def search_knowledge(
    q: str,
    limit: int = 8,
    audited_only: bool = True,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    svc = KnowledgeIndexService(db)
    return APIResponse(data=await svc.retrieve(q, limit=limit, audited_only=audited_only))


@router.post("/{chunk_id}/audit")
async def audit_knowledge(
    chunk_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin", "reviewer")),
):
    result = await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.id == chunk_id))
    chunk = result.scalar_one_or_none()
    if not chunk:
        raise HTTPException(404, "知识条目不存在")
    chunk.is_audited = True
    chunk.embedding = embed_text(chunk.content or "")
    await db.flush()
    return APIResponse(data={"id": chunk.id, "is_audited": True})


@router.delete("/{chunk_id}")
async def delete_knowledge(
    chunk_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    result = await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.id == chunk_id))
    chunk = result.scalar_one_or_none()
    if not chunk:
        raise HTTPException(404, "知识条目不存在")
    await db.delete(chunk)
    await db.flush()
    return APIResponse(data={"deleted": True})
