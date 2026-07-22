from __future__ import annotations

import re
from typing import Any


CHANNEL_LIMITS = {
    "email": 5000,
    "linkedin_dm": 1900,
    "twitter_dm": 280,
    "facebook_dm": 2000,
    "instagram_dm": 1000,
    "tiktok_dm": 1000,
}

RISK_PATTERNS = {
    "unsupported_guarantee": (
        r"\bguaranteed?\b",
        r"\b100%\s+(?:success|results?)\b",
        r"保证(?:成功|效果)",
    ),
    "invented_discount": (
        r"\bexclusive\s+\d+%\s+discount\b",
        r"\b\d+%\s+off\b",
        r"\d+%\s*折扣",
    ),
    "forbidden_greeting": (
        r"hope this email finds you well",
    ),
    "upfront_pricing": (
        r"\bprice\s+list\b",
        r"\bbest\s+price\b",
        r"\bcheap\b",
        r"\bquote\s+you\b",
        r"\bquotation\b",
    ),
}


def validate_message(message: dict[str, Any], evidence: list[str]) -> tuple[int, list[str]]:
    channel = str(message.get("channel") or "").strip()
    body = str(message.get("body") or "").strip()
    subject = str(message.get("subject") or "").strip()
    risk_flags: list[str] = []

    if channel not in CHANNEL_LIMITS:
        risk_flags.append("unsupported_channel")
    if not body:
        risk_flags.append("empty_body")
    if channel == "email" and not subject:
        risk_flags.append("missing_subject")
    if len(body) > CHANNEL_LIMITS.get(channel, 5000):
        risk_flags.append("channel_length_exceeded")

    lowered = body.casefold()
    if evidence and not any(item.casefold() in lowered for item in evidence if item.strip()):
        risk_flags.append("weak_personalization")

    combined = f"{subject}\n{body}"
    for flag, patterns in RISK_PATTERNS.items():
        if any(re.search(pattern, combined, re.IGNORECASE) for pattern in patterns):
            risk_flags.append(flag)

    score = 100
    penalties = {
        "unsupported_channel": 100,
        "empty_body": 100,
        "missing_subject": 20,
        "channel_length_exceeded": 35,
        "weak_personalization": 25,
        "unsupported_guarantee": 40,
        "invented_discount": 40,
        "forbidden_greeting": 60,
        "upfront_pricing": 40,
    }
    for flag in set(risk_flags):
        score -= penalties.get(flag, 10)
    return max(0, score), list(dict.fromkeys(risk_flags))
