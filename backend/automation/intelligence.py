"""Deterministic lead-intelligence helpers for webhook automation.

The local classifier keeps the desktop workflow usable without an external
model. Its output is structured so a hosted LLM provider can replace it later
without changing the automation engine or API contracts.
"""

from __future__ import annotations

import re
from typing import Any, Dict


INTENT_RULES = {
    "purchase": {
        "weight": 34,
        "keywords": (
            "buy",
            "purchase",
            "order",
            "采购",
            "购买",
            "下单",
        ),
    },
    "pricing": {
        "weight": 28,
        "keywords": (
            "price",
            "pricing",
            "quote",
            "cost",
            "budget",
            "价格",
            "报价",
            "费用",
            "预算",
        ),
    },
    "demo": {
        "weight": 26,
        "keywords": (
            "demo",
            "trial",
            "show me",
            "试用",
            "演示",
            "体验",
        ),
    },
    "integration": {
        "weight": 22,
        "keywords": (
            "api",
            "integration",
            "integrate",
            "webhook",
            "集成",
            "接口",
            "对接",
        ),
    },
    "support": {
        "weight": 12,
        "keywords": (
            "help",
            "issue",
            "problem",
            "support",
            "故障",
            "问题",
            "帮助",
            "客服",
        ),
    },
    "unsubscribe": {
        "weight": -50,
        "keywords": (
            "unsubscribe",
            "stop",
            "do not contact",
            "退订",
            "别联系",
            "不要联系",
        ),
    },
}

URGENCY_KEYWORDS = (
    "urgent",
    "asap",
    "today",
    "immediately",
    "尽快",
    "马上",
    "今天",
    "紧急",
)

HUMAN_REQUEST_KEYWORDS = (
    "human",
    "agent",
    "representative",
    "sales person",
    "人工",
    "真人",
    "销售",
    "客服人员",
)

POSITIVE_SIGNALS = (
    "company",
    "team",
    "enterprise",
    "volume",
    "monthly",
    "公司",
    "团队",
    "企业",
    "批量",
    "每月",
)


def _contains(text: str, keyword: str) -> bool:
    if keyword.isascii() and keyword.replace(" ", "").isalnum():
        return re.search(rf"\b{re.escape(keyword)}\b", text, re.IGNORECASE) is not None
    return keyword.casefold() in text.casefold()


def analyze_message(content: str, contact: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Classify intent and estimate lead quality from an inbound message."""

    text = (content or "").strip()
    contact = contact or {}
    matches: Dict[str, list[str]] = {}
    scores: Dict[str, int] = {}

    for intent, rule in INTENT_RULES.items():
        found = [keyword for keyword in rule["keywords"] if _contains(text, keyword)]
        if found:
            matches[intent] = found
            scores[intent] = rule["weight"] + min(12, (len(found) - 1) * 4)

    intent = max(scores, key=scores.get) if scores else "general"
    base_score = 18
    if intent != "unsubscribe":
        base_score += max(0, scores.get(intent, 0))
    else:
        base_score = 0

    positive_matches = [keyword for keyword in POSITIVE_SIGNALS if _contains(text, keyword)]
    urgency_matches = [keyword for keyword in URGENCY_KEYWORDS if _contains(text, keyword)]
    human_matches = [keyword for keyword in HUMAN_REQUEST_KEYWORDS if _contains(text, keyword)]

    score = base_score
    score += min(15, len(positive_matches) * 5)
    score += 8 if urgency_matches else 0
    score += 5 if contact.get("email") else 0
    score += 4 if len(text) >= 80 else 0
    score = max(0, min(100, score))

    if intent == "unsubscribe":
        temperature = "cold"
    elif score >= 70:
        temperature = "hot"
    elif score >= 40:
        temperature = "warm"
    else:
        temperature = "cold"

    confidence = 0.45
    if matches:
        confidence += min(0.4, sum(len(items) for items in matches.values()) * 0.08)
    if len(scores) == 1:
        confidence += 0.08
    confidence = round(min(0.95, confidence), 2)

    recommended_handoff = bool(human_matches) or score >= 80
    priority = "urgent" if urgency_matches or human_matches else ("high" if score >= 70 else "normal")
    reason = ""
    if human_matches:
        reason = "Contact explicitly requested a human response."
    elif score >= 80:
        reason = "High-intent lead reached the automatic handoff threshold."

    summary = _build_summary(intent, temperature, score, text)
    return {
        "intent": intent,
        "confidence": confidence,
        "score": score,
        "temperature": temperature,
        "priority": priority,
        "recommended_handoff": recommended_handoff,
        "handoff_reason": reason,
        "signals": {
            "intent_keywords": matches.get(intent, []),
            "positive_keywords": positive_matches,
            "urgency_keywords": urgency_matches,
            "human_request_keywords": human_matches,
        },
        "summary": summary,
        "generation_mode": "local_intelligence",
    }


def _build_summary(intent: str, temperature: str, score: int, content: str) -> str:
    excerpt = re.sub(r"\s+", " ", content).strip()
    if len(excerpt) > 120:
        excerpt = f"{excerpt[:117]}..."
    return f"{temperature.title()} lead ({score}/100), intent: {intent}. Message: {excerpt}"


def generate_smart_reply(context: Dict[str, Any], config: Dict[str, Any] | None = None) -> str:
    """Generate a concise intent-aware reply from structured local intelligence."""

    config = config or {}
    contact = context.get("contact") or {}
    intelligence = context.get("intelligence") or {}
    name = str(contact.get("name") or "there").strip()
    intent = intelligence.get("intent", "general")
    language = config.get("language", "auto")
    original = str((context.get("message") or {}).get("content", ""))
    use_chinese = language == "zh" or (language == "auto" and bool(re.search(r"[\u4e00-\u9fff]", original)))

    if use_chinese:
        replies = {
            "pricing": f"{name}，感谢咨询价格。我们已经记录您的需求，方便补充预计使用规模和预算范围吗？",
            "demo": f"{name}，可以安排产品演示。请告诉我您关注的使用场景和方便沟通的时间。",
            "purchase": f"{name}，感谢您的采购意向。请补充数量、交付时间和主要需求，我们会尽快跟进。",
            "integration": f"{name}，我们支持进一步评估集成方案。请说明目标系统、数据方向和预期上线时间。",
            "support": f"{name}，已收到您的问题。请补充具体报错或操作步骤，便于我们快速定位。",
            "unsubscribe": f"{name}，已记录您的请求，我们将停止后续自动联系。",
            "general": f"{name}，感谢您的消息。请告诉我您最希望解决的问题，我们会给出对应方案。",
        }
    else:
        replies = {
            "pricing": f"Hi {name}, thanks for asking about pricing. What usage volume and budget range should we plan for?",
            "demo": f"Hi {name}, we can arrange a product demo. Which use case and time window work best for you?",
            "purchase": f"Hi {name}, thanks for your purchase interest. Please share quantity, timeline, and key requirements.",
            "integration": f"Hi {name}, we can assess the integration. Which system, data flow, and launch timeline are involved?",
            "support": f"Hi {name}, we received your issue. Please share the error and steps to reproduce it.",
            "unsubscribe": f"Hi {name}, your request is recorded and automated follow-up will stop.",
            "general": f"Hi {name}, thanks for reaching out. What outcome are you trying to achieve?",
        }

    prefix = str(config.get("prefix") or "").strip()
    suffix = str(config.get("suffix") or "").strip()
    reply = replies.get(intent, replies["general"])
    return " ".join(part for part in (prefix, reply, suffix) if part)
