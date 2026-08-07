import hashlib
import math
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.models import KnowledgeChunk


def split_text(text: str, chunk_size: int = 700, overlap: int = 100) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        if start + chunk_size >= len(text):
            break
        start += max(1, chunk_size - overlap)
    return chunks


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    ascii_terms = re.findall(r"[a-z0-9_+-]{2,}", text)
    cjk_terms = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    bigrams = []
    for term in cjk_terms:
        bigrams.extend(term[i:i + 2] for i in range(max(0, len(term) - 1)))
    return ascii_terms + cjk_terms + bigrams


def embed_text(text: str, dim: int | None = None) -> list[float]:
    dim = dim or settings.EMBEDDING_DIM
    vector = [0.0] * dim
    for token in tokenize(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[idx] += sign
    norm = math.sqrt(sum(v * v for v in vector))
    if not norm:
        return vector
    return [round(v / norm, 6) for v in vector]


def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.0
    size = min(len(a), len(b))
    return sum(a[i] * b[i] for i in range(size))


class KnowledgeIndexService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_material(
        self,
        material_name: str,
        material_type: str,
        content: str,
        product_line: str = "",
        source_page: int = 1,
        audited: bool = False,
    ) -> list[KnowledgeChunk]:
        chunks = []
        for idx, chunk_text in enumerate(split_text(content), start=1):
            chunk = KnowledgeChunk(
                material_name=material_name,
                material_type=material_type,
                product_line=product_line,
                content=chunk_text,
                source_page=source_page,
                title_path=f"{material_name} / chunk-{idx}",
                is_audited=audited,
                access_level="internal",
                embedding=embed_text(chunk_text),
            )
            self.db.add(chunk)
            chunks.append(chunk)
        await self.db.flush()
        return chunks

    async def rebuild_index(self, material_type: str | None = None) -> dict:
        query = select(KnowledgeChunk)
        if material_type:
            query = query.where(KnowledgeChunk.material_type == material_type)
        result = await self.db.execute(query)
        chunks = result.scalars().all()
        for chunk in chunks:
            chunk.embedding = embed_text(chunk.content or "")
        await self.db.flush()
        return {
            "indexed_chunks": len(chunks),
            "embedding_dim": settings.EMBEDDING_DIM,
            "index_version": "hash-vector-v1",
        }

    async def retrieve(self, query_text: str, limit: int = 8, audited_only: bool = True) -> list[dict]:
        query_vector = embed_text(query_text)
        query_terms = Counter(tokenize(query_text))
        stmt = select(KnowledgeChunk).where(KnowledgeChunk.is_expired == False)
        if audited_only:
            stmt = stmt.where(KnowledgeChunk.is_audited == True)
        result = await self.db.execute(stmt)
        chunks = result.scalars().all()

        ranked = []
        for chunk in chunks:
            if not chunk.embedding:
                chunk.embedding = embed_text(chunk.content or "")
            chunk_terms = Counter(tokenize(chunk.content or ""))
            keyword_score = sum(min(query_terms[t], chunk_terms[t]) for t in query_terms)
            vector_score = cosine_similarity(query_vector, chunk.embedding)
            score = vector_score * 0.75 + min(keyword_score / 8, 1.0) * 0.25
            ranked.append((score, vector_score, keyword_score, chunk))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "id": chunk.id,
                "material_name": chunk.material_name,
                "material_type": chunk.material_type,
                "content_snippet": (chunk.content or "")[:300],
                "source_page": chunk.source_page,
                "is_audited": chunk.is_audited,
                "score": round(score, 4),
                "vector_score": round(vector_score, 4),
                "keyword_score": keyword_score,
            }
            for score, vector_score, keyword_score, chunk in ranked[:limit]
        ]
