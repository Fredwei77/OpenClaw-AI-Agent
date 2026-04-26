"""
Marketing Agent - 营销自动化 Agent
整合线索提取、评分、触达的完整营销工作流

功能：
1. 跨平台线索整合
2. Lead Scoring（评分）
3. 个性化内容生成
4. 多渠道触达协调
5. 营销漏斗分析
"""

import os
import sys
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent


@dataclass
class MarketingLead:
    """营销线索数据结构"""
    lead_id: int
    platform: str
    username: str
    profile_url: str
    email: Optional[str]
    followers: int
    engagement_score: float
    lead_score: float  # 0-100
    tier: str  # A, B, C
    tags: List[str]


class MarketingAgent(BaseAgent):
    """
    营销自动化 Agent

    工作流程：
    1. 从多个平台收集线索
    2. 进行 Lead Scoring
    3. 分层管理
    4. 生成个性化触达内容
    5. 协调执行触达
    """

    # 评分权重
    SCORING_WEIGHTS = {
        "followers": 0.25,        # 关注者数量
        "engagement": 0.30,       # 互动率
        "completeness": 0.20,     # 资料完整度
        "activity": 0.15,          # 活跃度
        "relevance": 0.10          # 关键字相关性
    }

    # 分层阈值
    TIER_THRESHOLDS = {
        "A": 75,  # 高价值线索
        "B": 50,  # 中等价值
        "C": 0    # 低价值
    }

    def __init__(self, name: str = "MarketingAgent", browser_manager=None, db=None):
        super().__init__(name, browser_manager, db)

    async def run(self, task: dict) -> Dict:
        """
        执行营销工作流

        Args:
            task: {
                "action": str,           # leads_collection | scoring | segmentation | outreach | full_flow
                "platforms": List[str],  # 目标平台
                "keywords": List[str],    # 关键字
                "leads": List[Dict],     # 已有线索（用于评分）
                "outreach_config": Dict   # 触达配置
            }

        Returns:
            Dict: 执行结果
        """
        action = task.get("action", "full_flow")
        platforms = task.get("platforms", ["linkedin", "twitter"])
        keywords = task.get("keywords", [])

        print(f"[MarketingAgent] Running marketing workflow: {action}")

        results = {}

        if action == "full_flow":
            # 完整工作流
            results = await self._full_marketing_flow(task)
        elif action == "leads_collection":
            results = await self._collect_leads(platforms, keywords)
        elif action == "scoring":
            results = await self._score_leads(task.get("leads", []))
        elif action == "segmentation":
            results = await self._segment_leads(task.get("leads", []))
        elif action == "outreach":
            results = await self._execute_outreach(task.get("leads", []), task.get("outreach_config", {}))
        else:
            raise ValueError(f"Unknown action: {action}")

        return results

    async def _full_marketing_flow(self, task: dict) -> Dict:
        """执行完整营销工作流"""
        platforms = task.get("platforms", ["linkedin", "twitter"])
        keywords = task.get("keywords", [])
        outreach_config = task.get("outreach_config", {})

        # Step 1: 收集线索
        print("[MarketingAgent] Step 1: Collecting leads...")
        leads = await self._collect_leads(platforms, keywords)

        # Step 2: Lead Scoring
        print("[MarketingAgent] Step 2: Scoring leads...")
        scored_leads = await self._score_leads(leads.get("leads", []))

        # Step 3: 分层
        print("[MarketingAgent] Step 3: Segmenting leads...")
        segmented = await self._segment_leads(scored_leads.get("scored_leads", []))

        # Step 4: 触达（如果配置了）
        outreach_results = {}
        if outreach_config.get("enabled"):
            print("[MarketingAgent] Step 4: Executing outreach...")
            outreach_results = await self._execute_outreach(
                segmented.get("segmented_leads", []),
                outreach_config
            )

        return {
            "leads_collected": leads.get("total", 0),
            "scored_leads": scored_leads.get("total", 0),
            "segmentation": segmented.get("summary", {}),
            "outreach": outreach_results
        }

    async def _collect_leads(self, platforms: List[str], keywords: List[str]) -> Dict:
        """从多个平台收集线索"""
        all_leads = []

        for platform in platforms:
            for keyword in keywords:
                try:
                    # 导入对应的 agent
                    if platform == "linkedin":
                        from agents.linkedin_agent.linkedin_agent import LinkedInAgent
                        agent = LinkedInAgent(browser_manager=self.browser_manager, db=self.db)
                    elif platform in ["twitter", "x"]:
                        from agents.twitter_agent.twitter_agent import TwitterAgent
                        agent = TwitterAgent(browser_manager=self.browser_manager, db=self.db)
                    else:
                        continue

                    leads = await agent.run({
                        "keyword": keyword,
                        "limit": 20
                    })
                    all_leads.extend(leads)

                except Exception as e:
                    print(f"[MarketingAgent] Failed to collect from {platform}/{keyword}: {e}")

        return {
            "leads": all_leads,
            "total": len(all_leads),
            "platforms": platforms,
            "keywords": keywords
        }

    async def _score_leads(self, leads: List[Dict]) -> Dict:
        """对线索进行评分"""
        scored = []

        for lead in leads:
            score = self._calculate_lead_score(lead)
            tier = self._get_tier(score)

            scored_lead = {
                **lead,
                "lead_score": score,
                "tier": tier,
                "scored_at": datetime.now().isoformat()
            }
            scored.append(scored_lead)

        # 按分数排序
        scored.sort(key=lambda x: x["lead_score"], reverse=True)

        return {
            "scored_leads": scored,
            "total": len(scored),
            "average_score": sum(l["lead_score"] for l in scored) / len(scored) if scored else 0
        }

    def _calculate_lead_score(self, lead: Dict) -> float:
        """计算线索综合评分 (0-100)"""
        score = 0.0

        # 关注者评分 (0-100)
        followers = lead.get("followers", 0)
        followers_score = min(100, (followers / 1000) * 100)
        score += followers_score * self.SCORING_WEIGHTS["followers"]

        # 资料完整度评分
        completeness = 0
        if lead.get("email"):
            completeness += 25
        if lead.get("profile_url"):
            completeness += 25
        if lead.get("followers", 0) > 0:
            completeness += 25
        if lead.get("tags"):
            completeness += 25
        score += completeness * self.SCORING_WEIGHTS["completeness"]

        # 关键字相关性评分
        relevance = 50  # 基础分
        tags = lead.get("tags", [])
        if tags:
            relevance += min(50, len(tags) * 10)
        score += relevance * self.SCORING_WEIGHTS["relevance"]

        return min(100, score)

    def _get_tier(self, score: float) -> str:
        """根据分数确定分层"""
        if score >= self.TIER_THRESHOLDS["A"]:
            return "A"
        elif score >= self.TIER_THRESHOLDS["B"]:
            return "B"
        else:
            return "C"

    async def _segment_leads(self, leads: List[Dict]) -> Dict:
        """将线索分层"""
        segments = {"A": [], "B": [], "C": []}
        summary = {"A": 0, "B": 0, "C": 0}

        for lead in leads:
            tier = lead.get("tier", "C")
            if tier in segments:
                segments[tier].append(lead)
                summary[tier] += 1

        return {
            "segmented_leads": leads,
            "segments": segments,
            "summary": summary
        }

    async def _execute_outreach(self, leads: List[Dict], config: Dict) -> Dict:
        """执行触达"""
        tier_priority = config.get("tier_priority", ["A", "B", "C"])
        max_per_tier = config.get("max_per_tier", {"A": 20, "B": 10, "C": 5})

        outreach_leads = []
        for tier in tier_priority:
            tier_leads = [l for l in leads if l.get("tier") == tier][:max_per_tier.get(tier, 0)]
            outreach_leads.extend(tier_leads)

        if not outreach_leads:
            return {"message": "No leads to outreach", "total": 0}

        # 使用 Email Agent 发送
        from agents.email_agent.email_agent import EmailAgent
        email_agent = EmailAgent()

        emails = [
            {
                "email": lead.get("email"),
                "lead_id": lead.get("id"),
                "vars": {
                    "name": lead.get("username", "").split()[0] if lead.get("username") else "there",
                    "company": lead.get("tags", [""])[0] if lead.get("tags") else "",
                    "topic": lead.get("tags", [""])[0] if lead.get("tags") else "business"
                }
            }
            for lead in outreach_leads
            if lead.get("email")
        ]

        result = await email_agent.run({
            "emails": emails,
            "template": config.get("template", "cold_outreach"),
            "template_vars": config.get("template_vars", {}),
            "campaign_id": config.get("campaign_id", "")
        })

        return result


# Standalone execution
async def execute_marketing_task(task: dict) -> Dict:
    """Execute marketing workflow"""
    agent = MarketingAgent()
    return await agent.run(task)


marketing_agent = MarketingAgent
