#!/usr/bin/env python3
"""Seed a small local Mock demo project.

The script is idempotent by project name: rerunning it reuses the existing
project and only creates missing demo records.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.application.knowledge_service import embed_text
from app.core.config import settings
from app.core.database import async_session, init_db
from app.domain.models import (
    Document,
    DocumentPage,
    KnowledgeChunk,
    Project,
    ProjectFact,
    Requirement,
    WorkflowStatus,
)


DEMO_PROJECT_NAME = "BidPilot-AI Mock 演示项目"
DEMO_OWNER_ID = "user_bm_001"
DEMO_OWNER_NAME = "投标经理"

MAIN_TENDER = """项目名称：城市服务 AI 中台建设项目
招标人：示范市数据资源局
项目预算：人民币 350 万元
工期：120 日历天
投标截止时间：2026年09月15日 10:00

资格要求：
投标人必须提供有效营业执照、软件著作权证明和近三年同类项目案例。
项目经理须具备信息系统项目管理师证书。

技术要求：
系统必须支持私有化部署、统一身份认证、日志审计和数据权限隔离。
售后服务响应时间不得超过 4 小时。

评分项：
技术方案完整性 30 分；同类案例 15 分；项目团队 10 分；售后服务 10 分。
"""

ADDENDUM = """补遗文件 001
针对城市服务 AI 中台建设项目，现对招标文件作如下修改：
1. 项目工期由 120 日历天调整为 90 日历天。
2. 售后服务响应时间由 4 小时调整为 2 小时。
3. 项目经理证书要求保持不变。
"""

QUALIFICATION = """企业资质材料
企业具备有效营业执照和软件著作权登记证书。
已完成智慧园区中台、政务数据治理平台等同类项目。
注意：本地演示材料故意不包含项目经理信息系统项目管理师证书，用于展示高风险缺失。
"""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _ensure_document(project_id: str, name: str, doc_type: str, content: str, uploaded_by: str) -> Document:
    async with async_session() as session:
        existing = (await session.execute(
            select(Document).where(Document.project_id == project_id, Document.name == name)
        )).scalar_one_or_none()
        if existing:
            return existing

        project_dir = Path(settings.UPLOAD_DIR) / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        file_path = project_dir / name
        file_path.write_text(content, encoding="utf-8")

        doc = Document(
            project_id=project_id,
            name=name,
            document_type=doc_type,
            file_path=str(file_path),
            file_size=len(content.encode("utf-8")),
            file_hash=_sha256(content),
            parse_status="completed",
            page_count=1,
            uploaded_by=uploaded_by,
        )
        session.add(doc)
        await session.flush()
        session.add(DocumentPage(
            document_id=doc.id,
            page_number=1,
            text=content,
            parse_method="seed",
            table_count=0,
            quality_score=1.0,
        ))
        await session.commit()
        return doc


async def main() -> None:
    await init_db()
    async with async_session() as session:
        project = (await session.execute(
            select(Project).where(Project.name == DEMO_PROJECT_NAME)
        )).scalar_one_or_none()
        if not project:
            project = Project(
                name=DEMO_PROJECT_NAME,
                project_type="software",
                owner_id=DEMO_OWNER_ID,
                owner_name=DEMO_OWNER_NAME,
                workflow_status=WorkflowStatus.FILES_UPLOADED.value,
                description="本地 Mock 演示项目：包含主招标文件、补遗文件和企业资质材料。",
            )
            session.add(project)
            await session.flush()
        project_id = project.id
        await session.commit()

    main_doc = await _ensure_document(project_id, "demo-main-tender.txt", "tender_main", MAIN_TENDER, DEMO_OWNER_ID)
    addendum_doc = await _ensure_document(project_id, "demo-addendum-001.txt", "addendum", ADDENDUM, DEMO_OWNER_ID)
    qual_doc = await _ensure_document(project_id, "demo-company-qualification.txt", "qualification", QUALIFICATION, DEMO_OWNER_ID)

    async with async_session() as session:
        existing_fact = (await session.execute(
            select(ProjectFact).where(ProjectFact.project_id == project_id, ProjectFact.fact_key == "duration").limit(1)
        )).scalar_one_or_none()
        if not existing_fact:
            session.add(ProjectFact(
                project_id=project_id,
                fact_key="duration",
                fact_value="120 日历天",
                source_document_id=main_doc.id,
                source_page=1,
                confidence=0.9,
                confirmation_status="pending",
                risk_level="high",
            ))

        existing_req = (await session.execute(
            select(Requirement).where(
                Requirement.project_id == project_id,
                Requirement.requirement_text.like("%项目经理须具备信息系统项目管理师证书%"),
            ).limit(1)
        )).scalar_one_or_none()
        if not existing_req:
            session.add(Requirement(
                project_id=project_id,
                requirement_text="项目经理须具备信息系统项目管理师证书。",
                requirement_type="qualification",
                mandatory=True,
                risk_level="high",
                evidence_required="项目经理证书",
                source_document_id=main_doc.id,
                source_page=1,
                confidence=0.88,
                status="pending",
            ))

        existing_chunk = (await session.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.material_name == "Demo 企业资质材料").limit(1)
        )).scalar_one_or_none()
        if not existing_chunk:
            session.add(KnowledgeChunk(
                material_name="Demo 企业资质材料",
                material_type="qualification",
                content=QUALIFICATION,
                document_version="local-demo",
                source_page=1,
                title_path="Demo 企业资质材料",
                is_audited=True,
                embedding=embed_text(QUALIFICATION),
            ))

        await session.commit()

    print("Demo data initialized.")
    print(f"Project: {DEMO_PROJECT_NAME}")
    print(f"Project ID: {project_id}")
    print("Documents:")
    print(f"- {main_doc.name}: {main_doc.id}")
    print(f"- {addendum_doc.name}: {addendum_doc.id}")
    print(f"- {qual_doc.name}: {qual_doc.id}")


if __name__ == "__main__":
    asyncio.run(main())
