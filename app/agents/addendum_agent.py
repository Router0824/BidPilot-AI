import re


FACT_PATTERNS = {
    "budget": [r"(?:预算|项目预算|投资金额)[：:是为]?\s*(.+?)(?:\n|$)"],
    "duration": [r"(?:工期|建设周期)[：:是为]?\s*(.+?)(?:\n|$)"],
    "deadline": [r"(?:投标截止|截止时间|提交截止)[：:是为]?\s*(.+?)(?:\n|$)"],
    "warranty": [r"(?:质保期|维保期)[：:是为]?\s*(.+?)(?:\n|$)"],
    "deployment": [r"部署方式[：:是为]?\s*(.+?)(?:\n|$)"],
}


def normalize_value(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "").strip("。；;，,")


class AddendumAgent:
    async def detect_conflicts(self, project_id: str, db_session) -> dict:
        from sqlalchemy import select

        from app.application.document_service import DocumentService
        from app.domain.models import ConfirmationTask, Document, ProjectFact

        doc_service = DocumentService(db_session)
        docs = (await db_session.execute(
            select(Document).where(Document.project_id == project_id, Document.document_type == "addendum")
        )).scalars().all()
        if not docs:
            return {"detected_conflicts": 0, "conflicts": []}

        facts = (await db_session.execute(
            select(ProjectFact).where(ProjectFact.project_id == project_id)
        )).scalars().all()
        fact_map = {f.fact_key: f for f in facts}
        conflicts = []

        for doc in docs:
            pages = await doc_service.get_pages(doc.id)
            for page in pages:
                text = page.text or ""
                extracted = self._extract_facts(text)
                for key, new_value in extracted.items():
                    old_fact = fact_map.get(key)
                    if not old_fact:
                        continue
                    old_value = old_fact.fact_value or ""
                    if normalize_value(old_value) == normalize_value(new_value):
                        continue
                    conflict = {
                        "fact_key": key,
                        "old_value": old_value,
                        "new_value": new_value,
                        "source_document_id": doc.id,
                        "source_page": page.page_number,
                    }
                    task = ConfirmationTask(
                        project_id=project_id,
                        task_type="addendum_conflict",
                        resource_type="project_fact",
                        resource_id=old_fact.id,
                        candidate_value=conflict,
                        source_document_id=doc.id,
                        source_page=page.page_number,
                        risk_level="high",
                        conflicts=[conflict],
                        created_node="detect_addendum_conflicts",
                    )
                    db_session.add(task)
                    conflicts.append(conflict)

        await db_session.flush()
        return {"detected_conflicts": len(conflicts), "conflicts": conflicts}

    def _extract_facts(self, text: str) -> dict[str, str]:
        facts = {}
        for key, patterns in FACT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if value:
                        facts[key] = value[:500]
                    break
        return facts


addendum_agent = AddendumAgent()
