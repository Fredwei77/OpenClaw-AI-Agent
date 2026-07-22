from __future__ import annotations

from typing import Any


PRODUCT_LINE = "用户填写"
CORE_ADVANTAGE = "用户填写"
TARGET_MARKETS = ("Europe", "North America")
PRIORITY_CUSTOMERS = (
    "engineering distributor",
    "lighting contractor",
    "renovation company",
)

DISQUALIFIED_KEYWORDS = (
    "retail",
    "retailer",
    "consumer shop",
    "dropship",
    "dropshipping",
    "trading company",
    "broker",
    "middleman",
    "price only",
    "compare price",
    "quotation only",
    "只比价",
    "零售",
    "贸易倒爷",
)

PRIORITY_KEYWORDS = (
    "engineering distributor",
    "project distributor",
    "electrical distributor",
    "lighting distributor",
    "工程分销",
    "distributor",
    "lighting contractor",
    "facade lighting",
    "outdoor lighting",
    "project lighting",
    "亮化",
    "contractor",
    "renovation company",
    "fit-out",
    "interior renovation",
    "装修",
    "renovation",
)

PURCHASE_KEYWORDS = ("annual", "yearly", "bulk", "container", "project purchase", "采购量", "年度采购")
SUPPLIER_PAIN_KEYWORDS = ("delay", "lead time", "quality issue", "supplier", "stock", "痛点", "交期", "现货")
DECISION_KEYWORDS = ("owner", "founder", "director", "procurement", "buyer", "project manager", "决策", "采购")
URGENCY_KEYWORDS = ("urgent", "asap", "tender", "project due", "deadline", "紧急", "投标", "赶工")

FORBIDDEN_EMAIL_PHRASES = (
    "hope this email finds you well",
    "exclusive discount",
    "% off",
    "price list",
    "best price",
    "cheap",
)


def lead_text(lead: dict[str, Any], research: dict[str, Any] | None = None) -> str:
    values: list[str] = []
    for source in (lead, research or {}):
        for key in ("username", "platform", "profile_url", "email", "status", "industry", "summary", "bio", "description", "company", "title"):
            value = source.get(key)
            if value:
                values.append(str(value))
        for key in ("tags", "interests", "talking_points"):
            for item in source.get(key) or []:
                if item:
                    values.append(str(item))
    return " ".join(values).casefold()


def is_disqualified_lead(lead: dict[str, Any], research: dict[str, Any] | None = None) -> bool:
    text = lead_text(lead, research)
    return any(keyword.casefold() in text for keyword in DISQUALIFIED_KEYWORDS)


def score_to_tier(score: int) -> str:
    if score >= 8:
        return "S"
    if score >= 5:
        return "A"
    if score >= 3:
        return "B"
    return "C"


def score_lead(lead: dict[str, Any], research: dict[str, Any] | None = None) -> dict[str, Any]:
    text = lead_text(lead, research)
    if is_disqualified_lead(lead, research):
        return {
            "score": 0,
            "tier": "C",
            "breakdown": {
                "industry_fit": 0,
                "annual_purchase": 0,
                "supplier_pain": 0,
                "decision_access": 0,
                "urgency": 0,
            },
            "reason": "disqualified customer type",
        }

    industry_fit = 3 if any(keyword.casefold() in text for keyword in PRIORITY_KEYWORDS) else 0
    annual_purchase = 2 if any(keyword.casefold() in text for keyword in PURCHASE_KEYWORDS) else 0
    supplier_pain = 2 if any(keyword.casefold() in text for keyword in SUPPLIER_PAIN_KEYWORDS) else 0
    decision_access = 2 if lead.get("email") or any(keyword.casefold() in text for keyword in DECISION_KEYWORDS) else 0
    urgency = 1 if any(keyword.casefold() in text for keyword in URGENCY_KEYWORDS) else 0
    score = min(10, industry_fit + annual_purchase + supplier_pain + decision_access + urgency)
    return {
        "score": score,
        "tier": score_to_tier(score),
        "breakdown": {
            "industry_fit": industry_fit,
            "annual_purchase": annual_purchase,
            "supplier_pain": supplier_pain,
            "decision_access": decision_access,
            "urgency": urgency,
        },
        "reason": "matches scoring_rules.md",
    }


def first_specific_signal(lead: dict[str, Any], research: dict[str, Any] | None = None) -> str:
    research = research or {}
    for key in ("talking_points", "interests", "tags"):
        source = research if key in research else lead
        for item in source.get(key) or []:
            value = str(item).strip()
            if value:
                return value
    industry = str(research.get("industry") or "").strip()
    if industry and industry.lower() != "unknown":
        return industry
    platform = str(lead.get("platform") or "your public profile").strip()
    username = str(lead.get("username") or "").strip().lstrip("@")
    return f"{platform} profile @{username}" if username else platform


def product_line(product_context: str = "") -> str:
    return product_context.strip() or PRODUCT_LINE


def core_advantage() -> str:
    return CORE_ADVANTAGE


def initial_email_body(lead: dict[str, Any], research: dict[str, Any], product_context: str = "") -> str:
    signal = first_specific_signal(lead, research)
    product = product_line(product_context)
    advantage = core_advantage()
    return (
        f"I saw your work on {signal}.\n\n"
        f"We focus on {product}; the core advantage is {advantage}.\n\n"
        "Before discussing price, I would check whether the product spec, quantity, and project timing fit your current procurement plan.\n\n"
        "Do you want to check lead time or available stock first?"
    )


def subject_for_signal(signal: str) -> str:
    return f"{signal} - lead time or stock"
