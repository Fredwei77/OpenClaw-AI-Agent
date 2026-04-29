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
from dataclasses import dataclass, field

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


@dataclass
class OutreachMessage:
    """触达消息结构"""
    channel: str  # email, linkedin, twitter, facebook
    subject: str = ""
    opening_line: str = ""
    value_proposition: str = ""
    body: str = ""
    call_to_action: str = ""
    closing: str = ""
    tone: str = "professional"  # professional, casual, formal
    estimated_response_rate: float = 0.0


@dataclass
class CampaignReport:
    """营销活动报告"""
    campaign_id: str
    generated_at: str
    summary: Dict
    lead_segments: Dict
    outreach_messages: List[OutreachMessage]
    recommendations: List[str]
    metrics: Dict = field(default_factory=dict)


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
        self.from_name = os.getenv("SENDER_NAME", "OpenClaw Team")

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

    async def generate_personalized_message(
        self,
        lead: Dict,
        channel: str = "email",
        tone: str = "professional"
    ) -> OutreachMessage:
        """
        AI 生成个性化触达消息

        Args:
            lead: 线索数据
            channel: 触达渠道 (email, linkedin, twitter)
            tone: 语气风格 (professional, casual, formal)

        Returns:
            OutreachMessage: 结构化的触达消息
        """
        # 分析线索特征
        name = lead.get("username", "").split()[0] if lead.get("username") else "there"
        topic = lead.get("tags", [""])[0] if lead.get("tags") else "business"
        company = lead.get("tags", [""])[1] if len(lead.get("tags", [])) > 1 else "your company"
        platform = lead.get("platform", "social media")
        followers = lead.get("followers", 0)

        # 根据渠道选择不同的消息模板
        if channel == "email":
            return await self._generate_email_message(lead, name, topic, company, tone)
        elif channel == "linkedin":
            return await self._generate_linkedin_message(lead, name, topic, company, tone)
        elif channel == "twitter":
            return await self._generate_twitter_message(lead, name, topic, tone)
        else:
            return await self._generate_email_message(lead, name, topic, company, tone)

    async def _generate_email_message(
        self,
        lead: Dict,
        name: str,
        topic: str,
        company: str,
        tone: str
    ) -> OutreachMessage:
        """生成邮件消息"""

        # 根据线索评分调整消息长度和详细程度
        lead_score = lead.get("lead_score", 50)
        tier = lead.get("tier", "B")

        # A级客户 - 更详细、更个性化的消息
        if tier == "A":
            opening_lines = [
                f"Hi {name}, I've been following your impressive work in the {topic} space,",
                f"Hi {name}, your approach to {topic} caught my attention,",
                f"Hi {name}, I noticed how you're leading innovation in {topic},"
            ]
            value_props = [
                "We've helped similar companies achieve 3x growth in qualified leads while reducing acquisition costs by 45%.",
                "Our AI-powered system has helped businesses like yours automate outreach and scale their lead generation efforts.",
                "Companies in the {topic} space have seen remarkable results with our platform - typically 3x more leads within 60 days."
            ]
            ctas = [
                "Would you be open to a 20-minute call this week to explore if there's a potential fit?",
                "I'd love to share how we've helped similar businesses. Are you available for a quick chat?",
                "Would you be interested in seeing how we've helped companies like yours? Happy to share some examples."
            ]
        # B级客户 - 中等长度
        elif tier == "B":
            opening_lines = [
                f"Hi {name}, I came across your work on {topic} and wanted to reach out,",
                f"Hi {name}, I noticed you work in the {topic} space,",
            ]
            value_props = [
                "We help businesses automate lead generation and customer outreach.",
                "Our platform has helped companies like yours scale their sales pipeline.",
            ]
            ctas = [
                "Would you be interested in a brief call to learn more?",
                "Open to chatting if you're looking for ways to improve your lead generation?"
            ]
        # C级客户 - 简洁
        else:
            opening_lines = [f"Hi {name}, I noticed your work in {topic}."]
            value_props = ["We help companies automate their outbound sales process."]
            ctas = ["Worth a quick chat?"]

        import random
        msg = OutreachMessage(
            channel="email",
            subject=f"Quick question about {topic}",
            opening_line=random.choice(opening_lines),
            value_proposition=random.choice(value_props).replace("{topic}", topic),
            call_to_action=random.choice(ctas),
            tone=tone,
            estimated_response_rate=0.15 if tier == "A" else 0.08 if tier == "B" else 0.03
        )

        # 组合完整邮件正文
        msg.body = self._compose_email_body(msg, lead)

        return msg

    def _compose_email_body(self, msg: OutreachMessage, lead: Dict) -> str:
        """组合完整邮件正文"""
        name = lead.get("username", "").split()[0] if lead.get("username") else "there"
        topic = lead.get("tags", [""])[0] if lead.get("tags") else "business"

        body = f"""
<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5; }}
  .container {{ max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 32px 24px; text-align: center; }}
  .header h1 {{ color: #ffffff; margin: 0; font-size: 22px; font-weight: 600; }}
  .header p {{ color: rgba(255,255,255,0.85); margin: 8px 0 0; font-size: 14px; }}
  .content {{ padding: 32px 24px; }}
  .greeting {{ font-size: 16px; color: #1a1a2e; margin-bottom: 20px; }}
  .body-text {{ font-size: 15px; color: #4a4a68; line-height: 1.7; margin-bottom: 20px; }}
  .highlight-box {{ background: #f8f9ff; border-left: 4px solid #667eea; padding: 16px 20px; border-radius: 0 8px 8px 0; margin: 24px 0; }}
  .highlight-box p {{ margin: 0; color: #4a4a68; font-size: 14px; }}
  .cta-button {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff !important; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 600; font-size: 15px; margin: 20px 0; }}
  .signature {{ margin-top: 32px; padding-top: 24px; border-top: 1px solid #eee; }}
  .signature-name {{ font-size: 16px; color: #1a1a2e; font-weight: 600; margin-bottom: 4px; }}
  .signature-title {{ font-size: 13px; color: #888; }}
  .footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; background: #fafafa; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>OpenClaw AI Agent</h1>
    <p>Automated Lead Generation & Customer Acquisition</p>
  </div>
  <div class="content">
    <p class="greeting">Hi {name},</p>

    <p class="body-text">
      {msg.opening_line} I've been following your content and was impressed by your approach to {topic}.
    </p>

    <div class="highlight-box">
      <p><strong>What we do:</strong><br>
      {msg.value_proposition}</p>
    </div>

    <p class="body-text">
      I'd love to share how we've helped companies in the {topic} space scale their operations. {msg.call_to_action}
    </p>

    <center>
      <a href="#" class="cta-button">Schedule a Quick Call</a>
    </center>

    <div class="signature">
      <p class="signature-name">{self.from_name if hasattr(self, 'from_name') else 'OpenClaw Team'}</p>
      <p class="signature-title">Growth Specialist, OpenClaw AI</p>
    </div>
  </div>
  <div class="footer">
    <p>You're receiving this because you opted in via our website or subscribed to our newsletter.<br>
    To unsubscribe, <a href="#">click here</a>.</p>
  </div>
</div>
</body>
</html>
"""
        return body

    async def _generate_linkedin_message(
        self,
        lead: Dict,
        name: str,
        topic: str,
        company: str,
        tone: str
    ) -> OutreachMessage:
        """生成 LinkedIn 消息"""
        import random

        openings = [
            f"Hi {name}, I noticed your work in the {topic} space.",
            f"Hi {name}! Impressive work you've been doing in {topic}.",
            f"Hi {name}, your content on {topic} caught my attention."
        ]

        value_props = [
            "We help B2B companies automate their lead generation and outreach.",
            "Our AI platform has helped similar businesses 3x their qualified leads.",
            "Just thought you might find value in how we're helping companies scale."
        ]

        ctas = [
            "Open to a quick chat?",
            "Worth a brief call if you're interested.",
            "Let me know if you'd like to learn more!"
        ]

        msg = OutreachMessage(
            channel="linkedin",
            opening_line=random.choice(openings),
            value_proposition=random.choice(value_props),
            call_to_action=random.choice(ctas),
            tone=tone,
            estimated_response_rate=0.25  # LinkedIn typically has higher response rates
        )

        # LinkedIn 短消息
        msg.body = f"{msg.opening_line} {msg.value_proposition} {msg.call_to_action}"

        return msg

    async def _generate_twitter_message(
        self,
        lead: Dict,
        name: str,
        topic: str,
        tone: str
    ) -> OutreachMessage:
        """生成 Twitter/X 消息"""
        # Twitter 限制 280 字符
        import random

        openings = [
            f"Hi @{lead.get('username', '').replace('@', '')}, loved your content on {topic}!",
            f"Impressive work on {topic}! We help companies like yours scale.",
        ]

        bodies = [
            f"We've helped B2B companies 3x their leads. Worth a chat?",
            f"Similar companies have seen great results. Interested in learning more?",
        ]

        msg = OutreachMessage(
            channel="twitter",
            opening_line=random.choice(openings),
            value_proposition=random.choice(bodies),
            call_to_action="DM me or reply below!",
            tone=tone,
            estimated_response_rate=0.05  # Twitter has lower conversion
        )

        # 组合推文
        full_tweet = f"{msg.opening_line} {msg.value_proposition} {msg.call_to_action}"
        # 截断到 280 字符
        msg.body = full_tweet[:280] if len(full_tweet) > 280 else full_tweet

        return msg

    def generate_campaign_report(
        self,
        leads: List[Dict],
        outreach_results: Dict,
        campaign_id: str = ""
    ) -> CampaignReport:
        """
        生成营销活动报告

        Args:
            leads: 已评分的线索列表
            outreach_results: 触达执行结果
            campaign_id: 活动ID

        Returns:
            CampaignReport: 结构化的活动报告
        """
        # 统计各层级线索
        segments = {"A": [], "B": [], "C": []}
        for lead in leads:
            tier = lead.get("tier", "C")
            if tier in segments:
                segments[tier].append(lead)

        summary = {
            "total_leads": len(leads),
            "tier_a_count": len(segments["A"]),
            "tier_b_count": len(segments["B"]),
            "tier_c_count": len(segments["C"]),
            "average_score": sum(l.get("lead_score", 0) for l in leads) / len(leads) if leads else 0,
            "total_outreach": outreach_results.get("total", 0) if outreach_results else 0,
            "total_sent": outreach_results.get("sent", 0) if outreach_results else 0,
        }

        # 生成推荐
        recommendations = []
        if summary["tier_a_count"] > 0:
            recommendations.append(f"Priority outreach to {summary['tier_a_count']} Tier-A leads with highest conversion potential")
        if summary["average_score"] < 50:
            recommendations.append("Consider broadening keywords to attract higher-quality leads")
        if outreach_results.get("failed", 0) > outreach_results.get("sent", 1) * 0.1:
            recommendations.append("Email deliverability may need attention - check sender reputation")

        # 生成各层级的示例消息
        sample_messages = []
        for tier in ["A", "B", "C"]:
            tier_lead = segments[tier][0] if segments[tier] else None
            if tier_lead:
                # 同步生成示例消息
                msg = self._generate_sample_message_sync(tier_lead, "email", "professional")
                sample_messages.append(msg)

        return CampaignReport(
            campaign_id=campaign_id or datetime.now().strftime("%Y%m%d%H%M%S"),
            generated_at=datetime.now().isoformat(),
            summary=summary,
            lead_segments=segments,
            outreach_messages=sample_messages,
            recommendations=recommendations,
            metrics={
                "expected_response_rate": sum(m.estimated_response_rate for m in sample_messages) / len(sample_messages) if sample_messages else 0,
                "estimated_conversions": int(summary.get("total_outreach", 0) * 0.1)
            }
        )

    def _generate_sample_message_sync(self, lead: Dict, channel: str, tone: str) -> OutreachMessage:
        """同步生成示例消息（用于报告）"""
        name = lead.get("username", "").split()[0] if lead.get("username") else "there"
        topic = lead.get("tags", [""])[0] if lead.get("tags") else "business"
        tier = lead.get("tier", "B")

        if channel == "email":
            subject = f"Quick question about {topic}"

            if tier == "A":
                body = f"""Hi {name},

I've been following your work in the {topic} space and I'm impressed by your approach.

We help B2B companies like yours automate lead generation and customer acquisition. Companies similar to yours have achieved:
• 3x increase in qualified leads
• 45% reduction in acquisition costs
• 24/7 automated outreach

Would you be open to a 20-minute call this week to explore if there's a potential fit?

Best regards,
OpenClaw Team"""

            else:
                body = f"""Hi {name},

I noticed your work in the {topic} space. We help companies automate their outreach and lead generation.

Would you be interested in learning more?

Best,
OpenClaw Team"""

            return OutreachMessage(
                channel="email",
                subject=subject,
                body=body,
                call_to_action="Schedule a call" if tier == "A" else "Learn more",
                tone=tone,
                estimated_response_rate=0.15 if tier == "A" else 0.08
            )

        return OutreachMessage(channel=channel, body="Sample message", tone=tone)


# Standalone execution
async def execute_marketing_task(task: dict) -> Dict:
    """Execute marketing workflow"""
    agent = MarketingAgent()
    return await agent.run(task)


def generate_marketing_report(leads: List[Dict], outreach_results: Dict, campaign_id: str = "") -> Dict:
    """Generate a marketing campaign report (sync version for API responses)"""
    agent = MarketingAgent()
    report = agent.generate_campaign_report(leads, outreach_results, campaign_id)
    return {
        "campaign_id": report.campaign_id,
        "generated_at": report.generated_at,
        "summary": report.summary,
        "lead_segments": {
            "A_count": len(report.lead_segments.get("A", [])),
            "B_count": len(report.lead_segments.get("B", [])),
            "C_count": len(report.lead_segments.get("C", []))
        },
        "recommendations": report.recommendations,
        "metrics": report.metrics
    }


marketing_agent = MarketingAgent
