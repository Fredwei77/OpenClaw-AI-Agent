"""AI providers for structured lead qualification and reply generation."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from automation.intelligence import analyze_message, generate_smart_reply

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = os.getenv(
    "OPENROUTER_AUTOMATION_MODEL",
    os.getenv("OPENROUTER_MARKETING_MODEL", "qwen/qwen3-30b-a3b-instruct-2507"),
)
FALLBACK_MODELS = os.getenv(
    "OPENROUTER_AUTOMATION_FALLBACK_MODELS",
    os.getenv(
        "OPENROUTER_MARKETING_FALLBACK_MODELS",
        "google/gemini-2.5-flash,openai/gpt-4o-mini",
    ),
)


@dataclass
class AIResult:
    output: Dict[str, Any]
    provider: str
    model: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: Optional[str] = None


def _strip_fences(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _local_result(context: Dict[str, Any], language: str = "auto") -> AIResult:
    intelligence = analyze_message(
        str((context.get("message") or {}).get("content", "")),
        context.get("contact") or {},
    )
    intelligence["reply"] = generate_smart_reply(
        {**context, "intelligence": intelligence},
        {"language": language},
    )
    return AIResult(
        output=intelligence,
        provider="local",
        model="local-intelligence-v1",
        latency_ms=0,
    )


def _normalize_output(raw: Any, context: Dict[str, Any], language: str) -> Dict[str, Any]:
    fallback = _local_result(context, language).output
    if not isinstance(raw, dict):
        return fallback

    intent = str(raw.get("intent") or fallback["intent"]).strip().lower()[:50]
    if intent not in {"purchase", "pricing", "demo", "integration", "support", "unsubscribe", "general"}:
        intent = "general"
    try:
        score = max(0, min(100, int(raw.get("score", fallback["score"]))))
        confidence = max(0.0, min(1.0, float(raw.get("confidence", fallback["confidence"]))))
    except (TypeError, ValueError):
        score = fallback["score"]
        confidence = fallback["confidence"]

    reply = str(raw.get("reply") or fallback["reply"]).strip()[:10000]
    summary = str(raw.get("summary") or fallback["summary"]).strip()[:1000]
    recommended_handoff = bool(raw.get("recommended_handoff", fallback["recommended_handoff"]))
    handoff_reason = str(raw.get("handoff_reason") or fallback["handoff_reason"]).strip()[:1000]
    temperature = "hot" if score >= 70 else ("warm" if score >= 40 else "cold")
    priority = str(raw.get("priority") or fallback["priority"])
    if priority not in {"normal", "high", "urgent"}:
        priority = "urgent" if recommended_handoff else ("high" if score >= 70 else "normal")

    return {
        **fallback,
        "intent": intent,
        "score": score,
        "confidence": round(confidence, 4),
        "temperature": temperature,
        "priority": priority,
        "recommended_handoff": recommended_handoff,
        "handoff_reason": handoff_reason,
        "summary": summary,
        "reply": reply,
        "generation_mode": "openrouter",
    }


class AutomationAIProvider:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self._client: Optional[AsyncOpenAI] = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_key != "sk-or-v1-your-key-here")

    def _get_client(self) -> AsyncOpenAI:
        if not self.configured:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=OPENROUTER_BASE_URL)
        return self._client

    async def generate(
        self,
        context: Dict[str, Any],
        provider_mode: str = "hybrid",
        model: Optional[str] = None,
        language: str = "auto",
        timeout_seconds: int = 30,
    ) -> AIResult:
        if provider_mode == "local" or not self.configured:
            return _local_result(context, language)

        models = [
            model or DEFAULT_MODEL,
            *(item.strip() for item in FALLBACK_MODELS.split(",")),
        ]
        models = list(dict.fromkeys(item for item in models if item))
        system_prompt = """You are an AI sales qualification agent.
Return ONLY valid JSON with these fields:
intent: purchase|pricing|demo|integration|support|unsubscribe|general
score: integer 0-100
confidence: number 0-1
priority: normal|high|urgent
recommended_handoff: boolean
handoff_reason: string
summary: concise string
reply: concise customer-facing reply in the same language as the inbound message

Never invent prices, discounts, legal claims, guarantees, or unavailable product capabilities.
If the contact asks to stop, set intent=unsubscribe and reply with a brief confirmation."""
        user_prompt = json.dumps(
            {
                "contact": context.get("contact") or {},
                "message": context.get("message") or {},
                "conversation": context.get("conversation") or {},
            },
            ensure_ascii=False,
        )

        last_error = None
        started = time.perf_counter()
        for candidate in models:
            try:
                response = await self._get_client().chat.completions.create(
                    model=candidate,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=700,
                    timeout=timeout_seconds,
                    extra_headers={
                        "HTTP-Referer": "http://localhost:8000",
                        "X-Title": "OpenClaw AI Lead Automation",
                    },
                )
                raw = json.loads(_strip_fences(response.choices[0].message.content or ""))
                usage = response.usage
                return AIResult(
                    output=_normalize_output(raw, context, language),
                    provider="openrouter",
                    model=candidate,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                )
            except Exception as exc:
                last_error = exc
                logger.warning("Automation model %s failed: %s", candidate, exc)

        if provider_mode == "openrouter":
            raise RuntimeError(f"All automation models failed: {last_error}")
        fallback = _local_result(context, language)
        fallback.error = str(last_error)
        fallback.latency_ms = int((time.perf_counter() - started) * 1000)
        return fallback


automation_ai_provider = AutomationAIProvider()
