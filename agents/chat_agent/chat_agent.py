from __future__ import annotations

import json
import os
import re
from typing import Any, Optional
from urllib.parse import urlparse

from openai import AsyncOpenAI

from agents.base_agent import BaseAgent
from agents.outreach_standards import (
    FORBIDDEN_EMAIL_PHRASES,
    core_advantage,
    first_specific_signal,
    initial_email_body,
    is_disqualified_lead,
    product_line,
    score_lead,
    subject_for_signal,
)
from .validators import CHANNEL_LIMITS, validate_message


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = os.getenv(
    "OPENROUTER_CHAT_MODEL",
    os.getenv("OPENROUTER_MARKETING_MODEL", "qwen/qwen3-30b-a3b-instruct-2507"),
)


def _strip_fences(value: str) -> str:
    cleaned = (value or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value or ""))


def _lead_platform(lead: dict[str, Any]) -> str:
    platform = str(lead.get("platform") or "").lower()
    if platform not in {"", "duckduckgo", "google"}:
        return platform

    profile_url = str(lead.get("profile_url") or "").strip()
    host = urlparse(profile_url).netloc.lower().split(":", 1)[0].removeprefix("www.")
    domains = {
        "linkedin.com": "linkedin",
        "x.com": "x",
        "twitter.com": "x",
        "facebook.com": "facebook",
        "instagram.com": "instagram",
        "tiktok.com": "tiktok",
    }
    for domain, detected in domains.items():
        if host == domain or host.endswith(f".{domain}"):
            return detected
    return platform


class ChatAgent(BaseAgent):
    """Generate guarded outbound drafts from persisted lead research."""

    def __init__(self, browser_manager=None, db=None):
        super().__init__("ChatAgent", browser_manager, db)
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.client: Optional[AsyncOpenAI] = None

    async def run(self, task: dict) -> dict:
        lead = task["lead"]
        research = task.get("research") or {}
        product_context = str(task.get("product_context") or "").strip()
        language = task.get("language", "en")
        available_channels = self.available_channels(lead)
        requested_channels = task.get("channels")
        channels = (
            [channel for channel in requested_channels if channel in available_channels]
            if requested_channels
            else available_channels
        )
        if is_disqualified_lead(lead, research):
            raise ValueError("Lead is C-tier by target_market.md and should not receive outbound development")
        if not channels:
            raise ValueError("Lead does not have a reachable email or supported social channel")
        messages, provider, model = await self.generate(
            lead,
            research,
            product_context,
            language,
            channels,
        )
        return {"messages": messages, "provider": provider, "model": model}

    @staticmethod
    def available_channels(lead: dict[str, Any]) -> list[str]:
        channels = []
        if lead.get("email"):
            channels.append("email")
        platform = _lead_platform(lead)
        social_channel = {
            "linkedin": "linkedin_dm",
            "x": "twitter_dm",
            "twitter": "twitter_dm",
            "facebook": "facebook_dm",
            "instagram": "instagram_dm",
            "tiktok": "tiktok_dm",
        }.get(platform)
        if social_channel:
            channels.append(social_channel)
        return channels

    async def generate(
        self,
        lead: dict[str, Any],
        research: dict[str, Any],
        product_context: str,
        language: str,
        channels: list[str],
    ) -> tuple[list[dict[str, Any]], str, str]:
        channels = list(dict.fromkeys(channel for channel in channels if channel in CHANNEL_LIMITS))
        if not channels:
            raise ValueError("No supported delivery channel is available")

        evidence = self._evidence(lead, research)
        if not self.api_key or self.api_key == "sk-or-v1-your-key-here":
            return self._fallback_messages(lead, research, product_context, language, channels, evidence), "local", "local-chat-v1"

        if self.client is None:
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=OPENROUTER_BASE_URL)
        try:
            response = await self.client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": self._system_prompt(language, channels)},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "lead": lead,
                                "research": research,
                                "product_context": product_context,
                                "personalization_evidence": evidence,
                            },
                            ensure_ascii=False,
                            default=str,
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=1400,
                timeout=30,
            )
            parsed = json.loads(_strip_fences(response.choices[0].message.content or ""))
            messages = self._normalize_messages(parsed.get("messages"), channels, evidence, language)
            if messages:
                return messages, "openrouter", DEFAULT_MODEL
        except Exception:
            pass
        return self._fallback_messages(lead, research, product_context, language, channels, evidence), "local_fallback", "local-chat-v1"

    @staticmethod
    def _system_prompt(language: str, channels: list[str]) -> str:
        requested_language = "Chinese" if language == "zh" else "English"
        return f"""You write concise, factual B2B cold outreach that sounds human, specific, and respectful.
Return JSON only: {{"messages":[{{"channel":"","subject":"","body":"","cta":""}}]}}.
Generate exactly one message for each channel in: {channels}.
Write in {requested_language}. Use at least one supplied personalization_evidence phrase naturally.
When English is requested, every subject, body, and CTA must contain English only.
Use these five files as the only business standard:
- product_brief.md: main product is "用户填写"; core advantage is "用户填写".
- target_market.md: target Europe and North America; prioritize engineering distributors, lighting contractors, renovation companies; do not develop retailers, trading middlemen, or price-only contacts.
- scoring_rules.md: S=8-10, A=5-7, B=3-4, C=<3 abandon.
- email_style.md: direct professional tone; first sentence must mention the customer's specific project or product; do not quote price upfront; end by guiding the customer to ask about lead time or available stock; never use "hope this email finds you well".
- follow_up_sop.md: day 3 follow-up, day 7 case, day 14 project progress; after 30 days without reply downgrade to C.
Open with one verifiable observation about the recipient's project or product, connect it only to the supplied product context,
and end with a question about lead time or available stock. Avoid generic praise such as "great content" or "very stylish".
Do not repeat the username handle unnaturally. Keep Twitter/X messages under 240 characters when possible.
Do not invent prices, discounts, customer names, case studies, guarantees, product capabilities, or products not supplied by product_context.
Email requires a subject. Respect the supplied channel's character limit.
Use a low-pressure CTA and do not claim the contact opted in."""

    @staticmethod
    def _evidence(lead: dict[str, Any], research: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for item in research.get("talking_points") or []:
            if str(item).strip():
                values.append(str(item).strip())
        industry = str(research.get("industry") or "").strip()
        if industry and industry.lower() != "unknown":
            values.append(industry)
        for item in research.get("interests") or []:
            if str(item).strip():
                values.append(str(item).strip())
        for key in ("summary", "bio", "description", "company", "display_name"):
            value = str(research.get(key) or "").strip()
            if value and value.lower() != "unknown":
                values.append(value)
        for item in lead.get("tags") or []:
            value = str(item).strip()
            if value:
                values.append(value)
        if not values:
            platform = str(lead.get("platform") or "online").strip()
            username = str(lead.get("username") or "").strip().lstrip("@")
            values.append(f"your {platform} profile" if not username else f"your {platform} profile @{username}")
        return list(dict.fromkeys(values))[:6]

    def _normalize_messages(
        self,
        raw_messages: Any,
        channels: list[str],
        evidence: list[str],
        language: str,
    ) -> list[dict[str, Any]]:
        if not isinstance(raw_messages, list):
            return []
        by_channel = {
            str(item.get("channel") or ""): item
            for item in raw_messages
            if isinstance(item, dict)
        }
        normalized = []
        for channel in channels:
            item = by_channel.get(channel)
            if not item:
                return []
            body = str(item.get("body") or "").strip()
            subject = str(item.get("subject") or "").strip() if channel == "email" else ""
            cta = str(item.get("cta") or "").strip()
            combined = f"{subject}\n{body}\n{cta}".casefold()
            if any(phrase in combined for phrase in FORBIDDEN_EMAIL_PHRASES):
                return []
            if language == "en" and _contains_cjk(f"{subject}\n{body}\n{cta}"):
                return []
            if len(body) > CHANNEL_LIMITS[channel]:
                body = body[: CHANNEL_LIMITS[channel] - 3].rstrip() + "..."
            message = {
                "channel": channel,
                "subject": subject,
                "body": body,
                "cta": cta,
                "personalization_evidence": evidence,
            }
            quality_score, risk_flags = validate_message(message, evidence)
            message["quality_score"] = quality_score
            message["risk_flags"] = risk_flags
            normalized.append(message)
        return normalized

    def _fallback_messages(
        self,
        lead: dict[str, Any],
        research: dict[str, Any],
        product_context: str,
        language: str,
        channels: list[str],
        evidence: list[str],
    ) -> list[dict[str, Any]]:
        raw_name = str(research.get("display_name") or lead.get("username") or "there").strip()
        name = raw_name.split("(@", 1)[0].strip().lstrip("@") or "there"
        signal = first_specific_signal(lead, research)
        product = product_line(product_context)
        advantage = core_advantage()
        lead_score = score_lead(lead, research)
        # The Chat Agent workbench is English-first; a model language mismatch also falls back here.
        language = "en"
        messages = []
        for channel in channels:
            if language == "zh":
                subject = f"关于 {signal} 的一个交流想法" if channel == "email" else ""
                body = (
                    f"你好 {name}，我注意到你在 {signal} 方面的工作。"
                    f"我们正在帮助相关团队改进{offer}。如果这也是你当前关注的方向，"
                    "是否方便用几分钟交流一下现状？"
                )
                cta = "交流当前重点"
            else:
                subject = subject_for_signal(signal) if channel == "email" else ""
                if channel == "email":
                    body = initial_email_body(lead, research, product_context)
                else:
                    body = (
                        f"Hi {name}, I saw your work on {signal}. "
                        f"We focus on {product}; core advantage: {advantage}. "
                        "Should I check lead time or available stock for your current project?"
                    )
                cta = "Check lead time or stock"
            if len(body) > CHANNEL_LIMITS[channel]:
                body = body[: CHANNEL_LIMITS[channel] - 3].rstrip() + "..."
            message = {
                "channel": channel,
                "subject": subject,
                "body": body,
                "cta": cta,
                "personalization_evidence": evidence,
            }
            quality_score, risk_flags = validate_message(message, evidence)
            message["quality_score"] = quality_score
            message["risk_flags"] = risk_flags
            message["lead_score"] = lead_score["score"]
            message["lead_tier"] = lead_score["tier"]
            messages.append(message)
        return messages
