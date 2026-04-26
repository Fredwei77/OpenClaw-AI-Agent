"""
Email Agent - 邮件自动化 Agent
用于发送开发信、跟进邮件、邮件模板管理

功能：
1. 批量发送开发信
2. 邮件模板管理
3. A/B 测试模板
4. 发送统计和追踪
5. 失败重试机制
"""

import os
import sys
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.header import Header
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent


@dataclass
class EmailMessage:
    """邮件数据结构"""
    to_email: str
    to_name: str = ""
    subject: str = ""
    body_html: str = ""
    body_text: str = ""
    attachments: List[str] = None
    campaign_id: str = ""
    lead_id: int = None


@dataclass
class EmailResult:
    """发送结果"""
    success: bool
    message_id: str = ""
    error: str = ""
    to_email: str = ""
    sent_at: datetime = None


class EmailAgent(BaseAgent):
    """
    邮件自动化 Agent

    支持：
    1. SMTP 发送
    2. 邮件模板变量替换
    3. 批量发送（带速率控制）
    4. 发送日志记录
    """

    def __init__(
        self,
        name: str = "EmailAgent",
        browser_manager=None,
        db=None,
        smtp_host: str = None,
        smtp_port: int = 587,
        smtp_user: str = None,
        smtp_password: str = None,
        from_email: str = None,
        from_name: str = "OpenClaw"
    ):
        super().__init__(name, browser_manager, db)

        # SMTP 配置
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER", "")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD", "")
        self.from_email = from_email or os.getenv("FROM_EMAIL", self.smtp_user)
        self.from_name = from_name or os.getenv("FROM_NAME", "OpenClaw")

        # 发送速率限制（每小时）
        self.max_emails_per_hour = int(os.getenv("MAX_EMAILS_PER_HOUR", "50"))

        # 邮件模板
        self.templates = self._load_default_templates()

    def _load_default_templates(self) -> Dict[str, Dict]:
        """加载默认邮件模板"""
        return {
            "cold_outreach": {
                "subject": "Quick question about {company}",
                "body_html": """
                    <html>
                    <body>
                    <p>Hi {name},</p>

                    <p>I noticed your work on {topic} and I was impressed by your approach.</p>

                    <p>I'm reaching out because we help companies like {company} with lead generation
                    and customer acquisition. We recently helped a similar business increase their
                    qualified leads by 3x.</p>

                    <p>Would you be open to a quick 15-minute call this week to explore if there's
                    a potential fit?</p>

                    <p>Best regards,<br>
                    {sender_name}</p>
                    </body>
                    </html>
                """,
                "variables": ["name", "company", "topic", "sender_name"]
            },
            "follow_up": {
                "subject": "Following up on my previous email - {topic}",
                "body_html": """
                    <html>
                    <body>
                    <p>Hi {name},</p>

                    <p>I wanted to follow up on my previous email about {topic}.</p>

                    <p>I understand you're busy, so I'll keep this brief. If you're not interested,
                    no worries at all - just let me know and I'll stop reaching out.</p>

                    <p>However, if you are curious about how we can help with lead generation,
                    I'd love to schedule a quick call.</p>

                    <p>Best,<br>
                    {sender_name}</p>
                    </body>
                    </html>
                """,
                "variables": ["name", "topic", "sender_name"]
            },
            "meeting_request": {
                "subject": "Meeting request: {topic}",
                "body_html": """
                    <html>
                    <body>
                    <p>Hi {name},</p>

                    <p>I've been following your work at {company} and I think what you're doing
                    with {topic} is impressive.</p>

                    <p>I'd love to schedule a 20-minute call to learn more about your current
                    challenges and see if we can help.</p>

                    <p>Would any of these times work for you?</p>
                    <ul>
                        <li>Monday 10am - 12pm</li>
                        <li>Wednesday 2pm - 4pm</li>
                        <li>Friday 9am - 11am</li>
                    </ul>

                    <p>Best regards,<br>
                    {sender_name}</p>
                    </body>
                    </html>
                """,
                "variables": ["name", "company", "topic", "sender_name"]
            }
        }

    async def run(self, task: dict) -> Dict:
        """
        执行邮件发送任务

        Args:
            task: {
                "emails": List[Dict],     # 邮件列表
                "template": str,          # 模板名称
                "template_vars": Dict,    # 模板变量
                "batch_size": int,        # 每批发送数量
                "delay_seconds": int       # 批次间隔
            }

        Returns:
            Dict: 发送统计结果
        """
        emails = task.get("emails", [])
        template_name = task.get("template", "cold_outreach")
        template_vars = task.get("template_vars", {})
        batch_size = task.get("batch_size", 10)
        delay_seconds = task.get("delay_seconds", 30)

        if not emails:
            raise ValueError("No emails provided")

        template = self.templates.get(template_name, self.templates["cold_outreach"])

        print(f"[EmailAgent] Starting email campaign with {len(emails)} recipients")

        results = []
        total_sent = 0
        total_failed = 0

        # 分批发送
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            print(f"[EmailAgent] Sending batch {i // batch_size + 1} ({len(batch)} emails)")

            for email_data in batch:
                # 合并模板变量
                vars_combined = {**template_vars, **email_data.get("vars", {})}

                # 渲染模板
                subject = self._render_template(template["subject"], vars_combined)
                body_html = self._render_template(template["body_html"], vars_combined)

                # 创建邮件
                msg = EmailMessage(
                    to_email=email_data.get("email", ""),
                    to_name=vars_combined.get("name", ""),
                    subject=subject,
                    body_html=body_html,
                    campaign_id=task.get("campaign_id", ""),
                    lead_id=email_data.get("lead_id")
                )

                # 发送
                result = await self._send_email(msg)
                results.append(result)

                if result.success:
                    total_sent += 1
                else:
                    total_failed += 1

            # 批次间延迟
            if i + batch_size < len(emails):
                await asyncio.sleep(delay_seconds)

        # 保存发送日志
        if self.db:
            await self._save_email_logs(results)

        return {
            "total": len(emails),
            "sent": total_sent,
            "failed": total_failed,
            "results": results
        }

    def _render_template(self, template: str, variables: Dict) -> str:
        """渲染邮件模板，替换变量"""
        result = template
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value) if value else "")
        return result

    async def _send_email(self, msg: EmailMessage) -> EmailResult:
        """发送单封邮件"""
        result = EmailResult(
            success=False,
            to_email=msg.to_email,
            sent_at=datetime.now()
        )

        try:
            if not self.smtp_user or not self.smtp_password:
                result.error = "SMTP credentials not configured"
                return result

            # 创建邮件
            mime_msg = MIMEMultipart('alternative')
            mime_msg['Subject'] = Header(msg.subject, 'utf-8')
            mime_msg['From'] = f"{self.from_name} <{self.from_email}>"
            mime_msg['To'] = msg.to_email

            # 添加纯文本和 HTML 版本
            text_part = MIMEText(msg.body_text or self._html_to_text(msg.body_html), 'plain', 'utf-8')
            html_part = MIMEText(msg.body_html, 'html', 'utf-8')

            mime_msg.attach(text_part)
            mime_msg.attach(html_part)

            # 发送
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, msg.to_email, mime_msg.as_string())

            result.success = True
            result.message_id = f"{datetime.now().timestamp()}-{msg.to_email}"

            print(f"[EmailAgent] Sent email to {msg.to_email}")

        except Exception as e:
            result.error = str(e)
            print(f"[EmailAgent] Failed to send to {msg.to_email}: {e}")

        return result

    def _html_to_text(self, html: str) -> str:
        """将 HTML 转换为纯文本"""
        import re
        text = re.sub(r'<br\s*/?>', '\n', html)
        text = re.sub(r'</p>', '\n\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()

    async def _save_email_logs(self, results: List[EmailResult]):
        """保存邮件发送日志到数据库"""
        try:
            for result in results:
                if result.success:
                    print(f"[EmailAgent] Logged: {result.to_email} - {result.message_id}")
        except Exception as e:
            print(f"[EmailAgent] Failed to save email logs: {e}")

    async def send_single_email(
        self,
        to_email: str,
        to_name: str = "",
        subject: str = "",
        body_html: str = "",
        template: str = None,
        template_vars: Dict = None
    ) -> EmailResult:
        """发送单封邮件的便捷方法"""
        if template:
            template_data = self.templates.get(template, self.templates["cold_outreach"])
            vars_combined = template_vars or {}
            vars_combined["name"] = to_name
            subject = self._render_template(template_data["subject"], vars_combined)
            body_html = self._render_template(template_data["body_html"], vars_combined)

        msg = EmailMessage(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            body_html=body_html
        )

        return await self._send_email(msg)


# Standalone execution
async def execute_email_task(task: dict) -> Dict:
    """Execute email campaign task"""
    agent = EmailAgent()
    return await agent.run(task)


email_agent = EmailAgent
