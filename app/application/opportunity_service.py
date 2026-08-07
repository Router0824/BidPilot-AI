import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Opportunity, OpportunityMonitor


SAMPLE_NOTICES = [
    {
        "title": "智慧政务平台升级改造采购公告",
        "url": "",
        "region": "全国",
        "summary": "包含平台建设、数据治理、运维服务等内容，适合作为商机监控样例。",
    },
    {
        "title": "医院信息化系统与安全加固项目招标公告",
        "url": "",
        "region": "全国",
        "summary": "覆盖医疗信息化、网络安全、等保测评与集成服务。",
    },
    {
        "title": "产业园区数字化管理平台建设项目竞争性磋商",
        "url": "",
        "region": "全国",
        "summary": "关注园区运营、物联感知、数据看板和项目实施能力。",
    },
]


class OpportunityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_monitors(self) -> list[OpportunityMonitor]:
        result = await self.db.execute(select(OpportunityMonitor).order_by(OpportunityMonitor.created_at.desc()))
        return result.scalars().all()

    async def create_monitor(self, data: dict, user: dict) -> OpportunityMonitor:
        monitor = OpportunityMonitor(
            name=data["name"][:255],
            source_url=data.get("source_url") or "",
            keywords=self._normalize_list(data.get("keywords")),
            regions=self._normalize_list(data.get("regions")),
            industry=(data.get("industry") or "")[:100],
            interval_minutes=int(data.get("interval_minutes") or 1440),
            enabled=bool(data.get("enabled", True)),
            created_by=user["id"],
        )
        self.db.add(monitor)
        await self.db.flush()
        return monitor

    async def list_opportunities(self, monitor_id: str | None = None, limit: int = 80) -> list[Opportunity]:
        stmt = select(Opportunity).order_by(Opportunity.heat_score.desc(), Opportunity.created_at.desc()).limit(limit)
        if monitor_id:
            stmt = stmt.where(Opportunity.monitor_id == monitor_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def run_monitor(self, monitor_id: str) -> dict:
        monitor = (await self.db.execute(select(OpportunityMonitor).where(OpportunityMonitor.id == monitor_id))).scalar_one_or_none()
        if not monitor:
            raise ValueError("商机监控不存在")
        notices = await self._fetch_notices(monitor)
        matched = [notice for notice in notices if self._matches(notice, monitor)]
        created = []
        for notice in matched[:30]:
            existing = await self._existing_opportunity(monitor.id, notice["title"], notice.get("url") or "")
            if existing:
                continue
            analysis = await self._analyze_notice(notice, monitor)
            opp = Opportunity(
                monitor_id=monitor.id,
                title=notice["title"][:500],
                url=(notice.get("url") or "")[:1000],
                source=self._source_name(monitor.source_url),
                region=notice.get("region") or self._matched_region(notice["title"], monitor.regions or []),
                industry=monitor.industry,
                publish_date=notice.get("publish_date") or "",
                summary=notice.get("summary") or "",
                matched_keywords=self._matched_keywords(f"{notice['title']} {notice.get('summary') or ''}", monitor.keywords or []),
                value_score=analysis["value_score"],
                competition_score=analysis["competition_score"],
                heat_score=analysis["heat_score"],
                ai_analysis=analysis,
            )
            self.db.add(opp)
            created.append(opp)
        monitor.last_run_at = datetime.now(timezone.utc)
        await self.db.flush()
        return {"fetched": len(notices), "matched": len(matched), "created": len(created)}

    async def refresh_all(self) -> dict:
        result = await self.db.execute(select(OpportunityMonitor).where(OpportunityMonitor.enabled == True))
        monitors = result.scalars().all()
        summaries = []
        for monitor in monitors:
            summaries.append({"monitor_id": monitor.id, **await self.run_monitor(monitor.id)})
        return {
            "monitors": len(monitors),
            "created": sum(item["created"] for item in summaries),
            "results": summaries,
        }

    def monitor_dict(self, monitor: OpportunityMonitor) -> dict:
        return {
            "id": monitor.id,
            "name": monitor.name,
            "source_url": monitor.source_url,
            "keywords": monitor.keywords or [],
            "regions": monitor.regions or [],
            "industry": monitor.industry,
            "enabled": monitor.enabled,
            "interval_minutes": monitor.interval_minutes,
            "last_run_at": str(monitor.last_run_at) if monitor.last_run_at else "",
            "created_at": str(monitor.created_at),
        }

    def opportunity_dict(self, opp: Opportunity) -> dict:
        return {
            "id": opp.id,
            "monitor_id": opp.monitor_id,
            "title": opp.title,
            "url": opp.url,
            "source": opp.source,
            "region": opp.region,
            "industry": opp.industry,
            "publish_date": opp.publish_date,
            "summary": opp.summary,
            "matched_keywords": opp.matched_keywords or [],
            "value_score": opp.value_score,
            "competition_score": opp.competition_score,
            "heat_score": opp.heat_score,
            "ai_analysis": opp.ai_analysis or {},
            "status": opp.status,
            "created_at": str(opp.created_at),
        }

    async def _fetch_notices(self, monitor: OpportunityMonitor) -> list[dict]:
        if not monitor.source_url:
            return SAMPLE_NOTICES
        try:
            async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
                response = await client.get(
                    monitor.source_url,
                    headers={"User-Agent": "BidPilot/1.0 opportunity-monitor"},
                )
                response.raise_for_status()
                html = response.text
        except Exception:
            return SAMPLE_NOTICES
        notices = self._parse_links(html, monitor.source_url)
        return notices or SAMPLE_NOTICES

    def _parse_links(self, html: str, base_url: str) -> list[dict]:
        html = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", "", html)
        links = []
        for match in re.finditer(r'(?is)<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html):
            title = self._strip_tags(match.group(2))
            if len(title) < 8:
                continue
            href = urljoin(base_url, unescape(match.group(1)))
            if not href.startswith(("http://", "https://")):
                continue
            links.append({"title": title[:500], "url": href, "region": "", "summary": title})
        deduped = []
        seen = set()
        for item in links:
            key = (item["title"], item["url"])
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped[:120]

    def _strip_tags(self, html: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"(?is)<[^>]+>", "", unescape(html))).strip()

    def _matches(self, notice: dict, monitor: OpportunityMonitor) -> bool:
        text = f"{notice.get('title') or ''} {notice.get('summary') or ''}"
        keywords = monitor.keywords or []
        regions = monitor.regions or []
        keyword_ok = not keywords or bool(self._matched_keywords(text, keywords))
        region_ok = not regions or bool(self._matched_region(text, regions))
        return keyword_ok and region_ok

    async def _existing_opportunity(self, monitor_id: str, title: str, url: str) -> Opportunity | None:
        stmt = select(Opportunity).where(Opportunity.monitor_id == monitor_id, Opportunity.title == title)
        if url:
            stmt = select(Opportunity).where(Opportunity.monitor_id == monitor_id, Opportunity.url == url)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _analyze_notice(self, notice: dict, monitor: OpportunityMonitor) -> dict:
        formula = self._formula_analysis(notice, monitor)
        formula["method"] = "fast-quantified"
        formula["llm_note"] = "列表刷新采用快速量化，避免逐条同步调用模型造成页面等待。"
        return formula

    def _formula_analysis(self, notice: dict, monitor: OpportunityMonitor) -> dict:
        text = f"{notice.get('title') or ''} {notice.get('summary') or ''}"
        matched_keywords = self._matched_keywords(text, monitor.keywords or [])
        value = 42 + min(len(matched_keywords) * 12, 30)
        if any(word in text for word in ("预算", "金额", "万元", "平台", "系统", "建设", "升级", "改造")):
            value += 14
        if monitor.industry and monitor.industry in text:
            value += 8

        competition = 48
        if any(word in text for word in ("公开招标", "综合评分", "平台", "大型")):
            competition += 16
        if any(word in text for word in ("竞争性磋商", "单一来源", "询价")):
            competition -= 8
        if len(matched_keywords) >= 2:
            competition -= 5

        value_score = self._score(value)
        competition_score = self._score(competition)
        heat_score = self._score(value_score * 0.68 + (100 - competition_score) * 0.32)
        return {
            "value_score": value_score,
            "competition_score": competition_score,
            "heat_score": heat_score,
            "reason": "按关键词命中、地区匹配、项目建设属性和竞争信号综合评分。",
            "action": "建议先核验公告原文、预算与资质门槛，再决定是否立项跟进。",
            "method": "formula",
        }

    def _matched_keywords(self, text: str, keywords: list[str]) -> list[str]:
        return [kw for kw in keywords if kw and kw.lower() in text.lower()]

    def _matched_region(self, text: str, regions: list[str]) -> str:
        return next((region for region in regions if region and region in text), "")

    def _source_name(self, source_url: str | None) -> str:
        if not source_url:
            return "样例源"
        parsed = urlparse(source_url)
        return parsed.netloc or source_url[:80]

    def _normalize_list(self, value) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in re.split(r"[,，\n\s]+", value) if item.strip()]
        return []

    def _score(self, value, default: float = 50) -> int:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = default
        return int(max(0, min(100, round(numeric))))
