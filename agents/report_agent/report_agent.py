"""
Report Agent - 数据报告和可视化 Agent
用于生成营销活动效果报告、数据分析

功能：
1. 多维度数据汇总
2. 可视化图表生成
3. 定时报告推送
4. 自定义报告模板
"""

import os
import sys
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent


@dataclass
class ReportSection:
    """报告章节"""
    title: str
    content: str
    data: Dict = None
    chart_type: str = None  # bar, line, pie, table


@dataclass
class Report:
    """完整报告"""
    title: str
    generated_at: datetime
    period: str
    sections: List[ReportSection]
    summary: Dict
    metrics: Dict


class ReportAgent(BaseAgent):
    """
    数据报告 Agent

    功能：
    1. 线索统计报告
    2. 营销活动效果报告
    3. 平台对比分析
    4. ROI 分析
    5. 定时任务报告
    """

    def __init__(self, name: str = "ReportAgent", browser_manager=None, db=None):
        super().__init__(name, browser_manager, db)

    async def run(self, task: dict) -> Dict:
        """
        生成报告

        Args:
            task: {
                "report_type": str,      # summary | campaign | platform | roi | custom
                "period": str,           # today | week | month | quarter | custom
                "start_date": str,       # YYYY-MM-DD (custom 时使用)
                "end_date": str,         # YYYY-MM-DD (custom 时使用)
                "platforms": List[str], # 平台过滤
                "output_format": str     # json | html | markdown
            }

        Returns:
            Dict: 报告数据
        """
        report_type = task.get("report_type", "summary")
        period = task.get("period", "week")
        platforms = task.get("platforms", [])
        output_format = task.get("output_format", "json")

        print(f"[ReportAgent] Generating {report_type} report for period: {period}")

        # 获取日期范围
        start_date, end_date = self._get_date_range(period, task)

        # 根据类型生成报告
        if report_type == "summary":
            report = await self._generate_summary_report(start_date, end_date, platforms)
        elif report_type == "campaign":
            report = await self._generate_campaign_report(start_date, end_date, platforms)
        elif report_type == "platform":
            report = await self._generate_platform_report(start_date, end_date)
        elif report_type == "roi":
            report = await self._generate_roi_report(start_date, end_date, platforms)
        else:
            report = await self._generate_custom_report(task)

        # 格式化输出
        if output_format == "html":
            return {"report": self._format_html(report)}
        elif output_format == "markdown":
            return {"report": self._format_markdown(report)}
        else:
            return {"report": report}

    def _get_date_range(self, period: str, task: dict) -> tuple:
        """获取日期范围"""
        end = datetime.now()

        if period == "today":
            start = end.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = end - timedelta(days=7)
        elif period == "month":
            start = end - timedelta(days=30)
        elif period == "quarter":
            start = end - timedelta(days=90)
        elif period == "custom":
            start = datetime.fromisoformat(task.get("start_date", end - timedelta(days=7)))
            end = datetime.fromisoformat(task.get("end_date", end))
        else:
            start = end - timedelta(days=7)

        return start, end

    async def _generate_summary_report(self, start_date: datetime, end_date: datetime, platforms: List[str]) -> Report:
        """生成汇总报告"""
        # 从数据库获取线索数据
        leads_data = await self._get_leads_data(start_date, end_date, platforms)
        tasks_data = await self._get_tasks_data(start_date, end_date)
        messages_data = await self._get_messages_data(start_date, end_date)

        # 计算指标
        total_leads = leads_data.get("total", 0)
        new_leads = leads_data.get("new", 0)
        total_tasks = tasks_data.get("total", 0)
        completed_tasks = tasks_data.get("completed", 0)
        total_messages = messages_data.get("sent", 0)
        success_rate = (messages_data.get("delivered", 0) / total_messages * 100) if total_messages > 0 else 0

        # 线索趋势
        leads_trend = leads_data.get("trend", [])

        sections = [
            ReportSection(
                title="Overview",
                content=f"Total leads collected: {total_leads}",
                data={
                    "total_leads": total_leads,
                    "new_leads": new_leads,
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "messages_sent": total_messages,
                    "delivery_rate": round(success_rate, 1)
                }
            ),
            ReportSection(
                title="Lead Generation",
                content=f"New leads this period: {new_leads}",
                data={"trend": leads_trend},
                chart_type="line"
            ),
            ReportSection(
                title="Task Execution",
                content=f"Tasks completed: {completed_tasks}/{total_tasks}",
                data=tasks_data.get("by_type", {}),
                chart_type="bar"
            )
        ]

        return Report(
            title="OpenClaw Summary Report",
            generated_at=datetime.now(),
            period=f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            sections=sections,
            summary={
                "total_leads": total_leads,
                "new_leads": new_leads,
                "conversion_rate": self._calculate_conversion(leads_data, messages_data),
                "engagement_rate": success_rate
            },
            metrics={
                "leads": leads_data,
                "tasks": tasks_data,
                "messages": messages_data
            }
        )

    async def _generate_campaign_report(self, start_date: datetime, end_date: datetime, platforms: List[str]) -> Report:
        """生成营销活动报告"""
        # 获取活动数据
        campaign_data = await self._get_campaign_data(start_date, end_date)

        sections = [
            ReportSection(
                title="Campaign Performance",
                content="Marketing campaign results",
                data=campaign_data,
                chart_type="bar"
            )
        ]

        return Report(
            title="Marketing Campaign Report",
            generated_at=datetime.now(),
            period=f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            sections=sections,
            summary=campaign_data.get("summary", {}),
            metrics=campaign_data
        )

    async def _generate_platform_report(self, start_date: datetime, end_date: datetime) -> Report:
        """生成平台对比报告"""
        platforms = ["linkedin", "twitter", "facebook", "instagram"]

        platform_stats = {}
        for platform in platforms:
            stats = await self._get_platform_stats(platform, start_date, end_date)
            platform_stats[platform] = stats

        sections = [
            ReportSection(
                title="Platform Comparison",
                content="Performance by platform",
                data=platform_stats,
                chart_type="bar"
            )
        ]

        return Report(
            title="Platform Performance Report",
            generated_at=datetime.now(),
            period=f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            sections=sections,
            summary={"best_platform": self._get_best_platform(platform_stats)},
            metrics=platform_stats
        )

    async def _generate_roi_report(self, start_date: datetime, end_date: datetime, platforms: List[str]) -> Report:
        """生成 ROI 报告"""
        roi_data = await self._calculate_roi(start_date, end_date)

        return Report(
            title="ROI Analysis Report",
            generated_at=datetime.now(),
            period=f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            sections=[],
            summary=roi_data.get("summary", {}),
            metrics=roi_data
        )

    async def _generate_custom_report(self, task: dict) -> Report:
        """生成自定义报告"""
        # 简化实现
        return Report(
            title="Custom Report",
            generated_at=datetime.now(),
            period="N/A",
            sections=[],
            summary={},
            metrics={}
        )

    async def _get_leads_data(self, start_date: datetime, end_date: datetime, platforms: List[str]) -> Dict:
        """获取线索数据"""
        # 模拟数据 - 实际应从数据库查询
        return {
            "total": 1250,
            "new": 342,
            "by_platform": {"linkedin": 500, "twitter": 400, "facebook": 350},
            "trend": [
                {"date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"), "count": 20 + i * 2}
                for i in range(7)
            ]
        }

    async def _get_tasks_data(self, start_date: datetime, end_date: datetime) -> Dict:
        """获取任务数据"""
        return {
            "total": 156,
            "completed": 134,
            "failed": 12,
            "pending": 10,
            "by_type": {"scrape": 80, "message": 50, "comment": 26}
        }

    async def _get_messages_data(self, start_date: datetime, end_date: datetime) -> Dict:
        """获取消息数据"""
        return {
            "sent": 856,
            "delivered": 789,
            "opened": 234,
            "clicked": 89
        }

    async def _get_campaign_data(self, start_date: datetime, end_date: datetime) -> Dict:
        """获取活动数据"""
        return {
            "summary": {
                "total_campaigns": 5,
                "active_campaigns": 2,
                "total_reach": 50000,
                "engagement_rate": 3.5
            },
            "campaigns": []
        }

    async def _get_platform_stats(self, platform: str, start_date: datetime, end_date: datetime) -> Dict:
        """获取平台统计"""
        return {
            "leads": random.randint(100, 500),
            "engagement": random.uniform(2, 8),
            "conversion": random.uniform(1, 5)
        }

    async def _calculate_roi(self, start_date: datetime, end_date: datetime) -> Dict:
        """计算 ROI"""
        return {
            "summary": {
                "total_spend": 5000,
                "leads_generated": 342,
                "cost_per_lead": 14.62,
                "conversion_rate": 2.5
            }
        }

    def _calculate_conversion(self, leads_data: Dict, messages_data: Dict) -> float:
        """计算转化率"""
        leads = leads_data.get("total", 0)
        messages = messages_data.get("sent", 0)
        if leads == 0 or messages == 0:
            return 0.0
        return round((messages / leads) * 100, 2)

    def _get_best_platform(self, platform_stats: Dict) -> str:
        """获取最佳平台"""
        best = None
        best_score = 0
        for platform, stats in platform_stats.items():
            score = stats.get("leads", 0) * stats.get("engagement", 0)
            if score > best_score:
                best_score = score
                best = platform
        return best or "N/A"

    def _format_html(self, report: Report) -> str:
        """格式化为 HTML"""
        html = f"""
        <html>
        <head><title>{report.title}</title></head>
        <body>
        <h1>{report.title}</h1>
        <p>Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M')}</p>
        <p>Period: {report.period}</p>
        """

        for section in report.sections:
            html += f"<h2>{section.title}</h2><p>{section.content}</p>"

        html += "</body></html>"
        return html

    def _format_markdown(self, report: Report) -> str:
        """格式化为 Markdown"""
        md = f"# {report.title}\n\n"
        md += f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        md += f"**Period:** {report.period}\n\n"

        for section in report.sections:
            md += f"## {section.title}\n\n{section.content}\n\n"

        return md


# Standalone execution
async def execute_report_task(task: dict) -> Dict:
    """Execute report generation"""
    agent = ReportAgent()
    return await agent.run(task)


import random
report_agent = ReportAgent
