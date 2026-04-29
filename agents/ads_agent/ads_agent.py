"""
Ads Agent - 广告投放管理 Agent
用于跨平台广告投放、效果追踪、优化

功能：
1. Facebook Ads 集成 (Marketing API)
2. Google Ads 集成
3. 广告效果追踪
4. 自动化优化
5. ROI 分析
"""

import os
import sys
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseAgent


@dataclass
class AdCampaign:
    """广告活动"""
    id: str
    name: str
    platform: str
    status: str
    budget: float
    spent: float
    impressions: int
    clicks: int
    conversions: int


class AdsAgent(BaseAgent):
    """
    广告投放管理 Agent

    支持平台：
    - Facebook Ads (via Marketing API)
    - Google Ads (via Google Ads API)
    """

    def __init__(
        self,
        name: str = "AdsAgent",
        browser_manager=None,
        db=None,
        facebook_token: str = None,
        google_credentials: str = None,
        google_developer_token: str = None
    ):
        super().__init__(name, browser_manager, db)

        self.facebook_token = facebook_token or os.getenv("FACEBOOK_ADS_TOKEN", "")
        self.facebook_account_id = os.getenv("FACEBOOK_ADS_ACCOUNT_ID", "")
        self.google_credentials = google_credentials or os.getenv("GOOGLE_ADS_CREDENTIALS", "")
        self.google_developer_token = google_developer_token or os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
        self.google_customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "")

    async def run(self, task: dict) -> Dict:
        """
        执行广告任务

        Args:
            task: {
                "action": str,           # create_campaign | pause_campaign | get_analytics | optimize | report
                "platform": str,         # facebook | google | all
                "campaign_data": Dict    # 活动数据
            }

        Returns:
            Dict: 执行结果
        """
        action = task.get("action", "get_analytics")
        platform = task.get("platform", "facebook")

        print(f"[AdsAgent] Running action: {action} on {platform}")

        try:
            if platform == "facebook" or platform == "all":
                return await self._run_facebook_action(action, task)
            elif platform == "google":
                return await self._run_google_action(action, task)
            else:
                return await self._run_facebook_action(action, task)
        except Exception as e:
            print(f"[AdsAgent] Error running action {action}: {e}")
            return {"error": str(e), "action": action, "platform": platform}

    async def _run_facebook_action(self, action: str, task: dict) -> Dict:
        """执行 Facebook Ads 操作"""
        if action == "create_campaign":
            return await self._facebook_create_campaign(task.get("campaign_data", {}))
        elif action == "pause_campaign":
            return await self._facebook_pause_campaign(task.get("campaign_id"))
        elif action == "get_analytics":
            return await self._facebook_get_analytics(task.get("date_range"))
        elif action == "optimize":
            return await self._facebook_optimize_campaign(task.get("campaign_id"))
        elif action == "report":
            return await self._facebook_generate_report(task.get("period"))
        elif action == "get_ad_sets":
            return await self._facebook_get_ad_sets(task.get("campaign_id"))
        elif action == "get_ads":
            return await self._facebook_get_ads(task.get("ad_set_id"))
        else:
            return {"error": f"Unknown action: {action}"}

    async def _run_google_action(self, action: str, task: dict) -> Dict:
        """执行 Google Ads 操作"""
        if action == "get_analytics":
            return await self._google_get_analytics(task.get("date_range"))
        elif action == "report":
            return await self._google_generate_report(task.get("period"))
        else:
            return {"error": f"Google Ads action '{action}' not yet implemented"}

    async def _facebook_api_request(self, endpoint: str, params: Dict = None) -> Dict:
        """
        向 Facebook Marketing API 发起请求
        """
        import aiohttp

        base_url = "https://graph.facebook.com/v18.0"
        url = f"{base_url}{endpoint}"
        params = params or {}

        if self.facebook_token:
            params["access_token"] = self.facebook_token

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    if "error" in data:
                        print(f"[AdsAgent] Facebook API error: {data['error']}")
                    return data
        except Exception as e:
            print(f"[AdsAgent] Facebook API request failed: {e}")
            return {"error": str(e)}

    async def _facebook_api_post(self, endpoint: str, data: Dict = None) -> Dict:
        """向 Facebook API 发起 POST 请求"""
        import aiohttp

        base_url = "https://graph.facebook.com/v18.0"
        url = f"{base_url}{endpoint}"
        data = data or {}

        if self.facebook_token:
            data["access_token"] = self.facebook_token

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    result = await response.json()
                    if "error" in result:
                        print(f"[AdsAgent] Facebook API error: {result['error']}")
                    return result
        except Exception as e:
            print(f"[AdsAgent] Facebook API post failed: {e}")
            return {"error": str(e)}

    async def _facebook_get_analytics(self, date_range: Dict = None) -> Dict:
        """获取 Facebook 广告分析数据"""
        if not self.facebook_token or not self.facebook_account_id:
            return self._mock_analytics("facebook", "Facebook Ads credentials not configured")

        # 默认最近7天
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        if date_range:
            start_date = datetime.fromisoformat(date_range.get("start", start_date.isoformat()))
            end_date = datetime.fromisoformat(date_range.get("end", end_date.isoformat()))

        # Facebook Marketing API 时间格式
        time_range = json.dumps({
            "since": start_date.strftime("%Y-%m-%d"),
            "until": end_date.strftime("%Y-%m-%d")
        })

        # 获取广告系列数据
        params = {
            "fields": "id,name,status,budget_remaining,daily_budget,lifetime_budget,spend,insights.date_preset(last_7d){impressions,clicks,reach,spend,ctr,cpc,actions,action_values}",
            "date_preset": "last_7d",
            "access_token": self.facebook_token
        }

        response = await self._facebook_api_request(
            f"/{self.facebook_account_id}/campaigns",
            params
        )

        if "error" in response:
            return self._mock_analytics("facebook", f"API Error: {response['error'].get('message', 'Unknown')}")

        campaigns = response.get("data", [])

        if not campaigns:
            return self._mock_analytics("facebook", "No campaigns found")

        formatted_campaigns = []
        total_spend = 0
        total_impressions = 0
        total_clicks = 0
        total_conversions = 0

        for camp in campaigns:
            insights = camp.get("insights", {}) or {}
            data = insights.get("data", [{}])[0] if insights.get("data") else {}

            # 提取转化数据
            actions = data.get("actions", [])
            conversions = 0
            conversion_value = 0
            for action in actions:
                if action.get("action_type") in ["purchase", "lead", "register"]:
                    conversions += int(action.get("value", 0))
                if action.get("action_type") == "purchase":
                    conversion_value = float(action.get("value", 0))

            spend = float(data.get("spend", 0))
            clicks = int(data.get("clicks", 0))
            impressions = int(data.get("impressions", 0))

            formatted_campaigns.append({
                "id": camp.get("id"),
                "name": camp.get("name"),
                "status": camp.get("status"),
                "budget": float(camp.get("daily_budget", 0)) if camp.get("daily_budget") else 0,
                "spent": spend,
                "impressions": impressions,
                "clicks": clicks,
                "ctr": round(clicks / impressions * 100, 2) if impressions > 0 else 0,
                "cpc": round(spend / clicks, 2) if clicks > 0 else 0,
                "conversions": conversions,
                "conversion_value": conversion_value,
                "roas": round(conversion_value / spend, 2) if spend > 0 and conversion_value > 0 else 0
            })

            total_spend += spend
            total_impressions += impressions
            total_clicks += clicks
            total_conversions += conversions

        return {
            "action": "get_analytics",
            "platform": "facebook",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_spend": round(total_spend, 2),
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "total_conversions": total_conversions,
                "average_ctr": round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0,
                "average_roas": round(total_conversions / len(formatted_campaigns), 1) if formatted_campaigns else 0
            },
            "campaigns": formatted_campaigns
        }

    async def _facebook_create_campaign(self, campaign_data: Dict) -> Dict:
        """创建 Facebook 广告活动"""
        if not self.facebook_token or not self.facebook_account_id:
            return self._mock_result("facebook", "Facebook Ads credentials not configured")

        name = campaign_data.get("name", "New Campaign")
        objective = campaign_data.get("objective", "LEAD_GEN")
        status = campaign_data.get("status", "PAUSED")
        daily_budget = campaign_data.get("daily_budget", 100)

        endpoint = f"/{self.facebook_account_id}/campaigns"
        params = {
            "name": name,
            "objective": objective,
            "status": status,
            "promoted_object": campaign_data.get("promoted_object", {}),
            "access_token": self.facebook_token
        }

        response = await self._facebook_api_post(endpoint, params)

        if "error" in response:
            return {"error": f"Failed to create campaign: {response['error'].get('message', 'Unknown')}"}

        return {
            "action": "create_campaign",
            "platform": "facebook",
            "campaign_id": response.get("id"),
            "name": name,
            "status": status,
            "daily_budget": daily_budget,
            "created_at": datetime.now().isoformat()
        }

    async def _facebook_pause_campaign(self, campaign_id: str) -> Dict:
        """暂停 Facebook 广告活动"""
        if not campaign_id:
            return {"error": "campaign_id is required"}

        if not self.facebook_token:
            return self._mock_result("facebook", "Facebook Ads credentials not configured")

        endpoint = f"/{campaign_id}"
        params = {
            "status": "PAUSED",
            "access_token": self.facebook_token
        }

        response = await self._facebook_api_post(endpoint, params)

        if "error" in response:
            return {"error": f"Failed to pause campaign: {response['error'].get('message', 'Unknown')}"}

        return {
            "action": "pause_campaign",
            "campaign_id": campaign_id,
            "platform": "facebook",
            "status": "paused",
            "paused_at": datetime.now().isoformat()
        }

    async def _facebook_optimize_campaign(self, campaign_id: str) -> Dict:
        """优化 Facebook 广告活动"""
        if not campaign_id:
            return {"error": "campaign_id is required"}

        # 获取当前广告系列表现
        params = {
            "fields": "id,name,insights.date_preset(last_7d){spend,clicks,ctr,cpc,actions}",
            "access_token": self.facebook_token
        }

        response = await self._facebook_api_request(f"/{campaign_id}", params)

        recommendations = []

        if "error" not in response:
            insights = response.get("insights", {})
            data = insights.get("data", [{}])[0] if insights.get("data") else {}

            spend = float(data.get("spend", 0))
            clicks = int(data.get("clicks", 0))
            ctr = float(data.get("ctr", 0))
            cpc = float(data.get("cpc", 0))

            actions = data.get("actions", [])
            conversions = sum(int(a.get("value", 0)) for a in actions if a.get("action_type") in ["purchase", "lead"])

            # 基于数据生成优化建议
            if ctr < 1:
                recommendations.append({
                    "type": "creative_improvement",
                    "current": f"CTR: {ctr}%",
                    "suggested": "Improve ad creative or targeting",
                    "reason": "Low CTR indicates ad creative may need improvement"
                })

            if conversions > 0:
                cpa = spend / conversions
                if cpa > 20:
                    recommendations.append({
                        "type": "audience_optimization",
                        "current": f"CPA: ${cpa:.2f}",
                        "suggested": "Narrow audience or improve landing page",
                        "reason": "High CPA suggests room for audience optimization"
                    })

            if spend > 0 and clicks > 0:
                recommendations.append({
                    "type": "bid_optimization",
                    "current": f"CPC: ${cpc:.2f}",
                    "suggested": "Consider automated bidding",
                    "reason": "Manual bidding may not be optimal for this campaign"
                })
        else:
            return {"error": f"Failed to get campaign data: {response['error'].get('message', 'Unknown')}"}

        return {
            "action": "optimize",
            "campaign_id": campaign_id,
            "platform": "facebook",
            "recommendations": recommendations,
            "potential_improvement": f"{len(recommendations)} optimizations available"
        }

    async def _facebook_generate_report(self, period: str = "7days") -> Dict:
        """生成 Facebook 广告报告"""
        days = int(period.replace("days", "")) if "days" in period else 7
        date_range = {
            "start": (datetime.now() - timedelta(days=days)).isoformat(),
            "end": datetime.now().isoformat()
        }

        analytics = await self._facebook_get_analytics(date_range)

        if "error" in analytics:
            return analytics

        suggestions = []
        for campaign in analytics.get("campaigns", []):
            roas = campaign.get("roas", 0)
            cpa = campaign.get("spent", 0) / campaign.get("conversions", 1) if campaign.get("conversions", 0) > 0 else 999

            if roas < 2:
                suggestions.append(f"Consider optimizing {campaign['name']} - ROAS is {roas}x (target: 2x+)")
            if cpa > 50:
                suggestions.append(f"Review targeting for {campaign['name']} - CPA is ${cpa:.2f}")

        return {
            "action": "report",
            "platform": "facebook",
            "period": period,
            "generated_at": datetime.now().isoformat(),
            "summary": analytics.get("summary", {}),
            "campaigns": analytics.get("campaigns", []),
            "suggestions": suggestions
        }

    async def _facebook_get_ad_sets(self, campaign_id: str) -> Dict:
        """获取广告系列下的广告组"""
        if not campaign_id:
            return {"error": "campaign_id is required"}

        if not self.facebook_token:
            return self._mock_result("facebook", "Facebook Ads credentials not configured")

        params = {
            "fields": "id,name,status,daily_budget,targeting,insights.date_preset(last_7d){impressions,clicks,spend}",
            "access_token": self.facebook_token
        }

        response = await self._facebook_api_request(f"/{campaign_id}/adsets", params)

        if "error" in response:
            return {"error": f"Failed to get ad sets: {response['error'].get('message', 'Unknown')}"}

        ad_sets = []
        for adset in response.get("data", []):
            insights = adset.get("insights", {}) or {}
            data = insights.get("data", [{}])[0] if insights.get("data") else {}

            ad_sets.append({
                "id": adset.get("id"),
                "name": adset.get("name"),
                "status": adset.get("status"),
                "daily_budget": adset.get("daily_budget"),
                "targeting": adset.get("targeting"),
                "impressions": int(data.get("impressions", 0)),
                "clicks": int(data.get("clicks", 0)),
                "spend": float(data.get("spend", 0))
            })

        return {
            "action": "get_ad_sets",
            "campaign_id": campaign_id,
            "ad_sets": ad_sets
        }

    async def _facebook_get_ads(self, ad_set_id: str) -> Dict:
        """获取广告组下的广告"""
        if not ad_set_id:
            return {"error": "ad_set_id is required"}

        if not self.facebook_token:
            return self._mock_result("facebook", "Facebook Ads credentials not configured")

        params = {
            "fields": "id,name,status,creative{title,body,image_url},insights.date_preset(last_7d){impressions,clicks,spend}",
            "access_token": self.facebook_token
        }

        response = await self._facebook_api_request(f"/{ad_set_id}/ads", params)

        if "error" in response:
            return {"error": f"Failed to get ads: {response['error'].get('message', 'Unknown')}"}

        ads = []
        for ad in response.get("data", []):
            insights = ad.get("insights", {}) or {}
            data = insights.get("data", [{}])[0] if insights.get("data") else {}
            creative = ad.get("creative", {}) or {}

            ads.append({
                "id": ad.get("id"),
                "name": ad.get("name"),
                "status": ad.get("status"),
                "title": creative.get("title", ""),
                "body": creative.get("body", ""),
                "image_url": creative.get("image_url", ""),
                "impressions": int(data.get("impressions", 0)),
                "clicks": int(data.get("clicks", 0)),
                "spend": float(data.get("spend", 0))
            })

        return {
            "action": "get_ads",
            "ad_set_id": ad_set_id,
            "ads": ads
        }

    async def _google_get_analytics(self, date_range: Dict = None) -> Dict:
        """获取 Google Ads 分析数据"""
        # Google Ads API 集成需要更复杂的 OAuth 设置
        # 当前返回模拟数据，未来可集成 Google Ads API
        return self._mock_analytics("google", "Google Ads API integration requires OAuth setup")

    async def _google_generate_report(self, period: str = "7days") -> Dict:
        """生成 Google Ads 报告"""
        return self._mock_analytics("google", "Google Ads API integration requires OAuth setup")

    def _mock_analytics(self, platform: str, message: str = None) -> Dict:
        """返回模拟分析数据"""
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        campaigns = [
            {
                "id": f"{platform}_1",
                "name": "Summer Sale Campaign",
                "status": "active",
                "budget": 500,
                "spent": 342.50,
                "impressions": 45000,
                "clicks": 890,
                "ctr": 1.98,
                "conversions": 23,
                "cpc": 0.38,
                "cpa": 14.89,
                "roas": 3.2
            },
            {
                "id": f"{platform}_2",
                "name": "New Product Launch",
                "status": "active",
                "budget": 300,
                "spent": 180.25,
                "impressions": 28000,
                "clicks": 520,
                "ctr": 1.86,
                "conversions": 15,
                "cpc": 0.35,
                "cpa": 12.02,
                "roas": 4.1
            }
        ]

        return {
            "action": "get_analytics",
            "platform": platform,
            "mock": True,
            "message": message or f"Using mock data for {platform}",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_spend": sum(c["spent"] for c in campaigns),
                "total_impressions": sum(c["impressions"] for c in campaigns),
                "total_clicks": sum(c["clicks"] for c in campaigns),
                "total_conversions": sum(c["conversions"] for c in campaigns),
                "average_ctr": sum(c["ctr"] for c in campaigns) / len(campaigns),
                "average_roas": sum(c["roas"] for c in campaigns) / len(campaigns)
            },
            "campaigns": campaigns
        }

    def _mock_result(self, platform: str, message: str) -> Dict:
        """返回模拟结果"""
        return {
            "action": "mock",
            "platform": platform,
            "message": message,
            "note": f"Configure {platform.upper()}_ADS_TOKEN for real integration"
        }


# Standalone execution
async def execute_ads_task(task: dict) -> Dict:
    """Execute ads task"""
    agent = AdsAgent()
    return await agent.run(task)


ads_agent = AdsAgent
