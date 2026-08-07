import json

from app.agents import BaseAgent, active_llm_gateway


class CommercialAgent(BaseAgent):
    async def generate(self, project_id: str, db_session) -> dict:
        context = await self._collect_context(project_id, db_session)
        if self.llm:
            messages = [
                {"role": "system", "content": "你是商务标编制专家。只输出JSON：{\"content\":\"...\"}。内容应覆盖报价说明、商务偏离、付款、交付、服务承诺，不得编造价格。"},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ]
            try:
                data = await self.call_llm("generate_commercial_bid", messages, "json", max_tokens=2600, temperature=0.2)
                content = data.get("content")
                if content:
                    return {"content": content, "agent": "commercial_agent"}
            except Exception:
                pass
        return {"content": self._fallback(context), "agent": "commercial_agent"}

    async def _collect_context(self, project_id: str, db_session) -> dict:
        from sqlalchemy import select
        from app.domain.models import Project, ProjectFact, Requirement

        project = (await db_session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        facts = (await db_session.execute(select(ProjectFact).where(ProjectFact.project_id == project_id))).scalars().all()
        reqs = (await db_session.execute(select(Requirement).where(Requirement.project_id == project_id, Requirement.requirement_type == "commercial"))).scalars().all()
        return {
            "project": {"name": project.name if project else project_id, "type": project.project_type if project else ""},
            "facts": {f.fact_key: f.fact_value for f in facts},
            "commercial_requirements": [r.requirement_text for r in reqs],
        }

    def _fallback(self, context: dict) -> str:
        name = context["project"]["name"]
        return f"""# 商务标响应

## 商务响应说明
针对{name}，我方将严格依据招标文件要求进行商务响应。

## 报价与付款
【待确认】请补充最终报价、付款节点、税率和有效期。

## 商务偏离
我方原则上无重大商务偏离；如存在差异，将在商务偏离表中逐项说明。

## 交付与服务承诺
我方承诺按招标文件约定完成交付、验收、培训和售后服务。
"""


class QualificationAgent(BaseAgent):
    async def generate(self, project_id: str, db_session) -> dict:
        context = await self._collect_context(project_id, db_session)
        if self.llm:
            messages = [
                {"role": "system", "content": "你是资格标编制专家。只输出JSON：{\"content\":\"...\"}。内容应覆盖投标人资格、证照、资质、业绩、人员，不得编造证书。"},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ]
            try:
                data = await self.call_llm("generate_qualification_bid", messages, "json", max_tokens=2600, temperature=0.2)
                content = data.get("content")
                if content:
                    return {"content": content, "agent": "qualification_agent"}
            except Exception:
                pass
        return {"content": self._fallback(context), "agent": "qualification_agent"}

    async def _collect_context(self, project_id: str, db_session) -> dict:
        from sqlalchemy import select
        from app.domain.models import KnowledgeChunk, Project, Requirement

        project = (await db_session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        reqs = (await db_session.execute(select(Requirement).where(Requirement.project_id == project_id, Requirement.requirement_type == "qualification"))).scalars().all()
        quals = (await db_session.execute(select(KnowledgeChunk).where(KnowledgeChunk.material_type == "qualification").limit(20))).scalars().all()
        return {
            "project": {"name": project.name if project else project_id, "type": project.project_type if project else ""},
            "qualification_requirements": [r.requirement_text for r in reqs],
            "qualification_materials": [{"name": q.material_name, "content": q.content} for q in quals],
        }

    def _fallback(self, context: dict) -> str:
        name = context["project"]["name"]
        return f"""# 资格标响应

## 投标人基本资格
针对{name}，我方将按招标文件要求提交主体资格、授权文件和相关证明材料。

## 资质与证书
【待确认】请补充营业执照、资质证书、管理体系认证等真实材料。

## 项目业绩
【待确认】请补充同类项目合同、验收证明或用户证明。

## 项目团队
【待确认】请补充项目经理、技术负责人和实施团队简历及证书。
"""


commercial_agent = CommercialAgent(active_llm_gateway)
qualification_agent = QualificationAgent(active_llm_gateway)
