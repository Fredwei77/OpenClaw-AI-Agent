from fastapi import APIRouter, HTTPException, Depends
import os
import sys
import asyncio
import json
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from openai import AsyncOpenAI
import traceback
import re
from datetime import datetime
from agents.outreach_standards import (
    PRIORITY_CUSTOMERS,
    TARGET_MARKETS,
    first_specific_signal,
    initial_email_body,
    is_disqualified_lead,
    score_lead,
    subject_for_signal,
)

from browser_cluster.manager.browser_pool import get_browser_pool
from scheduler.task_queue import get_task_queue, TaskPriority
from backend.email_utils import sanitize_lead_email
from .auth import get_current_user

router = APIRouter()
MAX_REASONABLE_FOLLOWERS = 10_000_000_000
CUSTOMER_RULES_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config", "customer_development_rules.json"))
_CUSTOMER_RULES_CACHE: dict[str, Any] | None = None
EMAIL_PATTERN = re.compile(r"(?i)\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b")
SEARCH_VERIFICATION_MARKERS = (
    "error-lite@duckduckgo.com",
    "duckduckgo.com/anomaly",
    "anomaly.js",
    "robot",
    "captcha",
    "verify you are human",
    "unusual traffic",
)
SOCIAL_RESULT_SKIP_TERMS = {
    "linkedin",
    "facebook",
    "instagram",
    "twitter",
    "x.com",
    "tiktok",
    "duckduckgo",
    "google",
}
SEARCH_RESULT_SKIP_HOSTS = {
    "duckduckgo.com",
    "google.com",
    "bing.com",
    "yahoo.com",
    "yandex.com",
    "baidu.com",
    "youtube.com",
    "amazon.com",
    "ebay.com",
    "pinterest.com",
    "reddit.com",
    "wikipedia.org",
}
PUBLIC_EMAIL_SKIP_HOSTS = {
    "linkedin.com",
    "x.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "google.com",
    "duckduckgo.com",
}
SOCIAL_SHORTLINK_HOSTS = {"t.co", "bit.ly", "lnkd.in", "linktr.ee", "bio.link", "beacons.ai"}
SOCIAL_LOW_VALUE_TERMS = {
    "fan",
    "fans",
    "girls",
    "girl",
    "hot",
    "sexy",
    "adult",
    "meme",
    "memes",
    "quote",
    "quotes",
    "daily",
    "every day",
    "community",
    "club",
    "blog",
    "tips",
    "review",
    "reviews",
}
SOCIAL_BUSINESS_SIGNAL_TERMS = {
    "manufacturer",
    "supplier",
    "factory",
    "wholesale",
    "distributor",
    "exporter",
    "importer",
    "brand",
    "store",
    "shop",
    "official",
    "company",
    "inc",
    "ltd",
    "llc",
    "apparel",
    "garment",
    "clothing",
    "wear",
    "lighting",
    "led",
    "equipment",
    "fitness",
    "yoga wear",
    "leggings",
}
COUNTRY_HINTS = {
    "United States": (".us", " united states", " usa", " u.s.", " california", " new york", " texas"),
    "United Kingdom": (".uk", " united kingdom", " london", " england", " scotland"),
    "Canada": (".ca", " canada", " toronto", " vancouver", " ontario"),
    "Australia": (".au", " australia", " sydney", " melbourne"),
    "Germany": (".de", " germany", " deutschland", " berlin"),
    "France": (".fr", " france", " paris"),
    "Japan": (".jp", " japan", " tokyo"),
    "Singapore": (".sg", " singapore"),
    "China": (".cn", " china", " shenzhen", " guangzhou", " shanghai"),
}
FUNDING_PATTERN = re.compile(
    r"(?i)\b(?:pre-seed|seed|series\s+[a-e]|angel|venture[-\s]?backed|bootstrapped|funded|raised\s+\$?[\d,.]+\s*(?:m|million|b|billion)?)\b"
)
EMPLOYEE_PATTERN = re.compile(
    r"(?i)\b(?:employees?|team size|company size|headcount)\D{0,20}(\d{1,3}(?:,\d{3})?)(?:\s*[-–]\s*(\d{1,3}(?:,\d{3})?))?"
)
EMPLOYEE_REVERSE_PATTERN = re.compile(
    r"(?i)\b(\d{1,3}(?:,\d{3})?)(?:\s*[-–]\s*(\d{1,3}(?:,\d{3})?))?\s+employees?\b"
)
FOUNDER_PATTERN = re.compile(
    r"(?i)\b(?:founder|co-founder|founded by|ceo)\s*(?:[:\-–]|is|was|,)?\s*([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})"
)


def _customer_development_rules() -> dict[str, Any]:
    global _CUSTOMER_RULES_CACHE
    if _CUSTOMER_RULES_CACHE is not None:
        return _CUSTOMER_RULES_CACHE
    try:
        with open(CUSTOMER_RULES_PATH, "r", encoding="utf-8") as file:
            _CUSTOMER_RULES_CACHE = json.load(file)
    except Exception as exc:
        print(f"[API] Customer rules unavailable: {exc}")
        _CUSTOMER_RULES_CACHE = {"version": "fallback", "asset_priority": []}
    return _CUSTOMER_RULES_CACHE


def _clean_company_asset_name(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -|•·")
    if not text:
        return ""
    cleanup = (_customer_development_rules().get("company_name_cleanup") or {})
    for term in cleanup.get("masked_terms") or []:
        if term and term.casefold() in text.casefold():
            return ""
    for pattern in cleanup.get("remove_patterns") or []:
        try:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip(" -|•·")
        except re.error:
            continue
    text = re.sub(r"\(@[A-Za-z0-9_]{1,15}\)", "", text).strip(" -|•·")
    text = re.sub(r"@[A-Za-z0-9_]{1,15}", "", text).strip(" -|•·")
    text = re.sub(r"\.{2,}|…", "", text).strip(" -|•·")
    text = re.sub(r"\s+@\w[\w.-]+$", "", text).strip(" -|•·")
    return text[:120]


def _searchable_company_name(lead: dict, keyword: str = "") -> str:
    metadata = lead.get("metadata") or {}
    for value in (
        metadata.get("company_name"),
        metadata.get("company"),
        metadata.get("organization"),
        metadata.get("title"),
        lead.get("username"),
    ):
        company = _clean_company_asset_name(str(value or ""))
        if company and len(company) >= 2:
            return company
    return str(keyword or "").strip()


def _tokenize_search_text(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]{3,}", str(text or "").casefold())
    stop = {"official", "website", "contact", "email", "company", "inc", "ltd", "llc", "limited", "the", "and"}
    deduped: list[str] = []
    for token in tokens:
        if token in stop:
            continue
        if token not in deduped:
            deduped.append(token)
    return deduped[:8]


def _is_search_result_host_allowed(url: str) -> bool:
    host = _host_from_url(url)
    if not host:
        return False
    blocked = SEARCH_RESULT_SKIP_HOSTS | PUBLIC_EMAIL_SKIP_HOSTS
    return not any(host == item or host.endswith(f".{item}") for item in blocked)


def _score_company_site_candidate(url: str, title: str, lead: dict, keyword: str = "") -> int:
    if not _is_email_lookup_candidate(url) or not _is_search_result_host_allowed(url):
        return -100
    host = _host_from_url(url)
    haystack = f"{host} {title}".casefold()
    company_tokens = _tokenize_search_text(_searchable_company_name(lead, keyword))
    keyword_tokens = _tokenize_search_text(keyword)
    score = 0
    if any(token in host for token in company_tokens):
        score += 6
    score += sum(2 for token in company_tokens if token in haystack)
    score += sum(1 for token in keyword_tokens if token in haystack)
    if re.search(r"/(?:contact|about|company|home)(?:[/#?]|$)", url, re.IGNORECASE):
        score += 1
    if len(host.split(".")) <= 3:
        score += 1
    if any(term in host for term in SOCIAL_RESULT_SKIP_TERMS):
        score -= 8
    return score


def _urls_from_text(text: str) -> list[str]:
    urls: list[str] = []
    for match in re.findall(r"(?i)\b(?:https?://)?(?:www\.)?[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>'\"]*)?", str(text or "")):
        url = match.strip(".,;)：:，。")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        if _is_email_lookup_candidate(url) and _is_search_result_host_allowed(url) and url not in urls:
            urls.append(url)
    return urls[:5]


def _candidate_url_from_social_anchor(href: str, text: str) -> str:
    href = str(href or "").strip()
    text = str(text or "").strip()
    host = _host_from_url(href)
    if host in {"x.com", "twitter.com"} and "/i/redirect" in href:
        from urllib.parse import parse_qs, unquote, urlparse

        target = parse_qs(urlparse(href).query).get("url", [""])[0]
        target = unquote(target)
        if _is_email_lookup_candidate(target) and _is_search_result_host_allowed(target):
            return target
    if host in SOCIAL_SHORTLINK_HOSTS or host.endswith(".t.co"):
        for url in _urls_from_text(text):
            if _is_email_lookup_candidate(url):
                return url
        return ""
    if href and _is_email_lookup_candidate(href) and _is_search_result_host_allowed(href):
        return href
    return ""


def _social_profile_url(lead: dict) -> str:
    profile_url = str(lead.get("profile_url") or "").strip()
    if profile_url and profile_url.startswith(("http://", "https://")):
        return profile_url
    platform = str(lead.get("platform") or "").casefold()
    username = str(lead.get("username") or "")
    handle_match = re.search(r"@([A-Za-z0-9_]{1,15})", username)
    if platform in {"x", "twitter"} and handle_match:
        return f"https://x.com/{handle_match.group(1)}"
    if profile_url and profile_url.startswith(("x.com/", "twitter.com/", "linkedin.com/", "www.linkedin.com/")):
        return f"https://{profile_url}"
    return ""


def _is_social_profile_lead(lead: dict) -> bool:
    platform = str(lead.get("platform") or "").casefold()
    if platform in {"x", "twitter", "linkedin", "facebook", "instagram", "tiktok"}:
        return True
    url = _social_profile_url(lead).casefold()
    return any(domain in url for domain in ("x.com/", "twitter.com/", "linkedin.com/", "facebook.com/", "instagram.com/", "tiktok.com/"))


def _has_social_business_signal(text: str, keyword: str = "") -> bool:
    haystack = f" {text or ''} {keyword or ''} ".casefold()
    return any(term in haystack for term in SOCIAL_BUSINESS_SIGNAL_TERMS)


def _is_low_value_social_lead(lead: dict, keyword: str = "") -> bool:
    """Filter social accounts that are unlikely to become B2B customer assets."""
    if not _is_social_profile_lead(lead):
        return False
    metadata = lead.get("metadata") or {}
    text = " ".join(
        str(value or "")
        for value in (
            lead.get("username"),
            lead.get("profile_url"),
            " ".join(lead.get("tags") or []),
            metadata.get("summary"),
            metadata.get("title"),
            metadata.get("company_name"),
        )
    ).casefold()
    if _asset_value(lead, "website", "linkedin_url", "email", "contact_email"):
        return False
    if _has_social_business_signal(text, keyword):
        return False
    return any(term in text for term in SOCIAL_LOW_VALUE_TERMS)


def _matches_keyword_intent(text: str, keyword: str) -> bool:
    """Reject social handles that only contain a keyword as part of another word."""
    terms = re.findall(r"[a-z0-9]{3,}", str(keyword or "").casefold())
    if not terms:
        return True
    haystack = str(text or "").casefold()
    return all(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack) for term in terms)


def _is_empty_social_asset_lead(lead: dict, keyword: str = "") -> bool:
    """Return true when a social result has no usable company asset fields."""
    if not _is_social_profile_lead(lead):
        return False
    metadata = lead.get("metadata") or {}
    if lead.get("email") or metadata.get("email") or metadata.get("contact_email"):
        return False
    if metadata.get("website") or metadata.get("linkedin_url"):
        return False
    platform = str(lead.get("platform") or "").casefold()
    profile_url = str(lead.get("profile_url") or "").casefold()
    if platform == "linkedin" and "linkedin.com/" in profile_url:
        return False
    return True


def _asset_value(lead: dict, *keys: str) -> str:
    metadata = lead.get("metadata") or {}
    for key in keys:
        value = metadata.get(key)
        if value:
            return str(value).strip()
    return ""


def _asset_field_status(lead: dict) -> dict[str, str]:
    metadata = lead.get("metadata") or {}
    fields = {
        "company_name": bool(_asset_value(lead, "company_name", "company", "organization", "title") or lead.get("username")),
        "website": bool(_asset_value(lead, "website", "official_website", "homepage", "company_website")),
        "founder": bool(_asset_value(lead, "founder", "founders", "owner", "ceo")),
        "linkedin_url": bool(_asset_value(lead, "linkedin_url", "linkedin", "linkedin_company_url") or "linkedin.com" in str(lead.get("profile_url") or "")),
        "email": bool(lead.get("email") or metadata.get("email") or metadata.get("contact_email")),
        "funding": bool(_asset_value(lead, "funding", "funding_status", "funding_round", "financing")),
        "employee_size": bool(_asset_value(lead, "employee_size", "employees", "employee_count", "company_size", "headcount")),
        "country": bool(_asset_value(lead, "country", "country_code", "location_country", "geography", "location")),
    }
    return {field: ("verified" if present else "missing") for field, present in fields.items()}


def _asset_presence_counts(leads: list[dict]) -> dict[str, int]:
    fields = ("website", "linkedin_url", "email", "country", "employee_size", "founder", "funding")
    counts = {field: 0 for field in fields}
    for lead in leads:
        metadata = lead.get("metadata") or {}
        if metadata.get("website"):
            counts["website"] += 1
        if metadata.get("linkedin_url") or "linkedin.com" in str(lead.get("profile_url") or ""):
            counts["linkedin_url"] += 1
        if lead.get("email") or metadata.get("email") or metadata.get("contact_email"):
            counts["email"] += 1
        for field in ("country", "employee_size", "founder", "funding"):
            if metadata.get(field):
                counts[field] += 1
    return counts


def _asset_debug_summary(leads: list[dict], keyword: str = "") -> dict[str, Any]:
    no_company = 0
    social_profiles = 0
    website_ready = 0
    samples = []
    for lead in leads:
        metadata = lead.get("metadata") or {}
        company = _searchable_company_name(lead, keyword)
        if not company:
            no_company += 1
        if _is_social_profile_lead(lead):
            social_profiles += 1
        if metadata.get("website"):
            website_ready += 1
        if len(samples) < 5:
            samples.append({
                "id": lead.get("id"),
                "company": company,
                "profile_url": lead.get("profile_url") or _social_profile_url(lead),
                "website": metadata.get("website"),
                "linkedin_url": metadata.get("linkedin_url"),
                "email": lead.get("email") or metadata.get("email"),
            })
    return {
        "keyword": keyword,
        "no_company_name": no_company,
        "social_profiles": social_profiles,
        "website_ready": website_ready,
        "samples": samples,
    }


def _asset_next_action(lead: dict, score: dict[str, Any]) -> str:
    metadata = lead.get("metadata") or {}
    status = metadata.get("asset_status") or _asset_field_status(lead)
    if score.get("tier") == "C" or metadata.get("disqualified"):
        return "abandon_or_low_frequency_nurture"
    if status.get("website") == "missing":
        return "find_official_website"
    if status.get("email") == "missing":
        return "find_public_business_email"
    if score.get("tier") in {"S", "A"}:
        return "start_personalized_outreach"
    return "monitor_until_project_signal"


def _apply_customer_development_rules(lead: dict) -> None:
    metadata = lead.get("metadata") or {}
    company = _clean_company_asset_name(
        metadata.get("company_name")
        or metadata.get("company")
        or metadata.get("organization")
        or metadata.get("title")
        or lead.get("username")
        or ""
    )
    if company:
        metadata["company_name"] = company
    if lead.get("email"):
        metadata.setdefault("email", lead["email"])
    scoring = score_lead(lead, metadata)
    metadata["rules_version"] = _customer_development_rules().get("version", "fallback")
    metadata["asset_status"] = _asset_field_status({**lead, "metadata": metadata})
    metadata["quality_score"] = scoring.get("score", 0)
    metadata["tier"] = scoring.get("tier", "C")
    metadata["score_breakdown"] = scoring.get("breakdown", {})
    metadata["disqualified"] = bool(is_disqualified_lead(lead, metadata))
    metadata["next_action"] = _asset_next_action({**lead, "metadata": metadata}, scoring)
    lead["metadata"] = metadata


def _extract_public_emails(text: str) -> list[str]:
    """Extract likely public business emails from visible text or HTML."""
    if not text:
        return []
    normalized = (
        text.replace("[at]", "@")
        .replace("(at)", "@")
        .replace(" at ", "@")
        .replace("[dot]", ".")
        .replace("(dot)", ".")
        .replace(" dot ", ".")
    )
    normalized = re.sub(r"\s*@\s*", "@", normalized)
    normalized = re.sub(r"\s*\.\s*", ".", normalized)
    emails = []
    for match in EMAIL_PATTERN.findall(normalized):
        email = match.strip(" .,:;<>[](){}'\"").lower()
        local, _, domain = email.partition("@")
        if not local or not domain:
            continue
        if domain.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
            continue
        if domain in {"example.com", "test.com", "email.com"}:
            continue
        email = sanitize_lead_email(email)
        if not email:
            continue
        if email not in emails:
            emails.append(email)
    return emails[:5]


def _first_public_email(text: str) -> str | None:
    emails = _extract_public_emails(text)
    return emails[0] if emails else None


def _is_email_lookup_candidate(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        from urllib.parse import urlparse

        host = urlparse(url).netloc.lower().split(":", 1)[0].removeprefix("www.")
    except Exception:
        return False
    return not any(host == item or host.endswith(f".{item}") for item in PUBLIC_EMAIL_SKIP_HOSTS)


def _clean_search_result_url(href: str) -> str:
    """Resolve common search redirect URLs into their target URL."""
    if not href:
        return ""
    from urllib.parse import parse_qs, unquote, urlparse

    if "/l/?" in href or "duckduckgo.com/l/" in href:
        target = parse_qs(urlparse(href).query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return href


def _host_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        return urlparse(url).netloc.lower().split(":", 1)[0].removeprefix("www.")
    except Exception:
        return ""


def _is_social_url(url: str) -> bool:
    host = _host_from_url(url)
    return any(host == item or host.endswith(f".{item}") for item in PUBLIC_EMAIL_SKIP_HOSTS)


def _clean_company_title(title: str, host: str = "") -> str:
    title = re.sub(r"\s+", " ", str(title or "")).strip(" -|•·")
    if not title:
        return ""
    for separator in (" | ", " - ", " – ", " — ", " :: "):
        if separator in title:
            title = title.split(separator, 1)[0].strip()
            break
    if host:
        root = host.split(".")[0].replace("-", " ")
        if title.casefold() in {"home", "homepage", "official website"}:
            title = root.title()
    return title[:120]


def _infer_country(url: str = "", text: str = "") -> str:
    host = _host_from_url(url)
    haystack = f" {host} {text or ''}".casefold()
    for country, hints in COUNTRY_HINTS.items():
        if any(hint in haystack for hint in hints):
            return country
    return ""


def _extract_asset_metadata(text: str, url: str = "", title: str = "") -> dict[str, str]:
    """Extract lightweight company asset fields from public search/page text."""
    metadata: dict[str, str] = {}
    text = re.sub(r"\s+", " ", text or "").strip()
    host = _host_from_url(url)
    cleaned_title = _clean_company_title(title, host)
    if cleaned_title:
        metadata["company_name"] = cleaned_title
        metadata["title"] = cleaned_title
    if url and not _is_social_url(url):
        metadata["website"] = url
        if host:
            metadata["domain"] = host
    if "linkedin.com" in (url or ""):
        metadata["linkedin_url"] = url
    linkedin_match = re.search(r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[^\s\"'<>]+", text, re.IGNORECASE)
    if linkedin_match:
        metadata["linkedin_url"] = linkedin_match.group(0).rstrip(").,")
    country = _infer_country(url, text)
    if country:
        metadata["country"] = country
    employee_match = EMPLOYEE_PATTERN.search(text) or EMPLOYEE_REVERSE_PATTERN.search(text)
    if employee_match:
        metadata["employee_size"] = (
            f"{employee_match.group(1)}-{employee_match.group(2)}"
            if employee_match.group(2)
            else employee_match.group(1)
        )
    funding_match = FUNDING_PATTERN.search(text)
    if funding_match:
        metadata["funding"] = funding_match.group(0).strip()
    founder_match = FOUNDER_PATTERN.search(text)
    if founder_match:
        metadata["founder"] = founder_match.group(1).strip(" .,;:-")
    return metadata


def _merge_metadata(lead: dict, metadata: dict[str, str]) -> None:
    if not metadata:
        return
    current = lead.get("metadata") or {}
    for key, value in metadata.items():
        if value and not current.get(key):
            current[key] = value
    lead["metadata"] = current


def _is_search_verification_page(text: str) -> bool:
    """Detect search-engine bot checks/error pages so their support emails are not captured."""
    if not text:
        return False
    lowered = text.casefold()
    return any(marker in lowered for marker in SEARCH_VERIFICATION_MARKERS)


def _lead_email_discovery_query(lead: dict, keyword: str = "") -> str:
    """Build a public web search query for discovering a company's contact page."""
    parts: list[str] = []
    username = str(lead.get("username") or "").strip()
    if username:
        username = re.sub(r"\([^)]*@[^)]*\)", "", username)
        username = re.sub(r"[@|•·]+", " ", username)
        username = re.sub(r"\s+", " ", username).strip()
        if username:
            parts.append(f'"{username[:80]}"')
    metadata = lead.get("metadata") or {}
    title = str(metadata.get("title") or metadata.get("summary") or "").strip()
    if title and len(title) <= 120:
        parts.append(title)
    if keyword:
        parts.append(keyword)
    parts.append("contact email")
    return " ".join(parts)


def _parse_social_count(text: str) -> int:
    """Parse follower counters without treating arbitrary text as a compact number."""
    if not text:
        return 0
    match = re.search(
        r"(?i)(\d[\d,]*(?:\.\d+)?)\s*([KMB])?\s*followers?\b",
        text,
    )
    if not match:
        match = re.fullmatch(r"\s*(\d[\d,]*(?:\.\d+)?)\s*([KMB])\s*", text, re.IGNORECASE)
    if not match:
        return 0
    number = float(match.group(1).replace(",", ""))
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[(match.group(2) or "").upper()]
    return min(int(number * multiplier), MAX_REASONABLE_FOLLOWERS)


def _auto_detect_chrome_user_data_dir() -> str | None:
    """Auto-detect Chrome user data directory when CHROME_USER_DATA_DIR is not set."""
    candidates = []
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            candidates.append(os.path.join(local_app_data, "Google", "Chrome", "User Data"))
            candidates.append(os.path.join(local_app_data, "Microsoft", "Edge", "User Data"))
    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        candidates.append(os.path.join(home, "Library", "Application Support", "Google", "Chrome"))
    else:
        home = os.path.expanduser("~")
        candidates.append(os.path.join(home, ".config", "google-chrome"))

    for d in candidates:
        if os.path.isdir(d) and os.path.isdir(os.path.join(d, "Default")):
            return d
    return None

# OpenRouter configuration
API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1"
MARKETING_MODEL = os.getenv("OPENROUTER_MARKETING_MODEL", "qwen/qwen3-30b-a3b-instruct-2507")
MARKETING_FALLBACK_MODELS = os.getenv(
    "OPENROUTER_MARKETING_FALLBACK_MODELS",
    "google/gemini-2.5-flash,google/gemini-2.5-flash-lite,openai/gpt-4o-mini",
)

# Module-level reusable client (created lazily on first use)
_llm_client: Optional[AsyncOpenAI] = None


def _get_llm_client() -> AsyncOpenAI:
    """Get or create a shared AsyncOpenAI client."""
    global _llm_client
    if _llm_client is None:
        if not API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY not configured")
        _llm_client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    return _llm_client


def _marketing_model_candidates() -> list[str]:
    models = [MARKETING_MODEL, *(model.strip() for model in MARKETING_FALLBACK_MODELS.split(","))]
    return list(dict.fromkeys(model for model in models if model))


async def _create_marketing_completion(client: AsyncOpenAI, *, messages: list[dict], max_tokens: int, temperature: float = 0.35):
    """Try configured OpenRouter marketing models in order before using local fallback."""
    last_error = None
    for model in _marketing_model_candidates():
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                extra_headers={"HTTP-Referer": "http://localhost:8000", "X-Title": "OpenClaw AI Agent"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response, model
        except Exception as exc:
            last_error = exc
            print(f"[MarketingModel] {model} failed: {exc}")
    raise RuntimeError(f"All configured marketing models failed: {last_error}")


# ========================
# Pydantic Models
# ========================

class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=12000)
    language: str = "en"


class ScrapeRequest(BaseModel):
    keyword: str = "fitness equipment"
    platform: str = "x"
    # 高级选项
    use_proxy: bool = False  # 是否使用代理
    store_domain: Optional[str] = None  # Shopify 店铺域名（如 mystore.myshopify.com）
    cookies: Optional[Dict[str, str]] = None  # 可选的登录态 Cookie
    # 扩展过滤参数
    geography: str = "all"  # 目标地区: all, us, uk, ca, au, de, fr, jp, sg
    follower_range: str = "all"  # 粉丝规模: all, 0-1k, 1k-10k, 10k-50k, 50k-100k, 100k+
    content_type: str = "all"  # 账号类型: all, influencer, business, creator, reseller
    max_results: int = 50  # 最大结果数量


class AssetEnrichmentRequest(BaseModel):
    lead_ids: list[int] = Field(default_factory=list, max_length=100)
    keyword: str = ""
    platform: str = "all"
    limit: int = Field(default=25, ge=1, le=100)


class TaskSubmitRequest(BaseModel):
    agent_name: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 1  # 0=LOW, 1=NORMAL, 2=HIGH, 3=URGENT
    platform: Optional[str] = None


class TaskStatusRequest(BaseModel):
    task_id: int


class MarketingPipelineRequest(BaseModel):
    lead_ids: list[int] = Field(..., min_length=1, max_length=20)
    product_context: str = ""
    language: str = "en"


class AcquisitionPlatform(BaseModel):
    platform: Literal[
        "x", "twitter", "linkedin", "instagram", "facebook", "tiktok",
        "shopify", "google", "duckduckgo", "directory",
    ]
    priority: int = Field(default=1, ge=0, le=3)


class AcquisitionPipelineRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=255)
    platforms: list[AcquisitionPlatform] = Field(..., min_length=1, max_length=10)
    max_results_per_platform: int = Field(default=25, ge=1, le=200)
    max_outreach_leads: int = Field(default=20, ge=1, le=20)
    product_context: str = Field(default="", max_length=2000)


def _ordered_acquisition_platforms(platforms: list[AcquisitionPlatform]) -> list[AcquisitionPlatform]:
    """Run higher priorities first while preserving request order for ties."""
    return sorted(platforms, key=lambda item: -item.priority)


class MarketingActionRequest(BaseModel):
    action: Literal["email", "classify", "social"]
    lead_ids: list[int] = Field(..., min_length=1, max_length=10)
    product_context: str = Field(default="", max_length=2000)
    language: Literal["zh", "en"] = "en"


def _is_usable_marketing_text(text: str, language: str = "en") -> bool:
    """Reject empty, corrupted, or obviously incoherent marketing output."""
    if not text or not 40 <= len(text.strip()) <= 8000:
        return False
    if any(marker in text for marker in ("\ufffd", "锛", "銆", "鈥", "馃")):
        return False
    if re.search(r"[A-Za-z]{36,}", text):
        return False
    if language == "en" and _contains_non_english_script(text):
        return False
    foreign_script_chars = re.findall(r"[\u0400-\u052f\u0590-\u05ff\u0600-\u06ff]", text)
    if len(foreign_script_chars) > 3:
        return False
    return True


def _contains_non_english_script(text: str) -> bool:
    """Detect scripts that should not appear in English outreach copy."""
    if not text:
        return False
    return bool(re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))


def _lead_summary(lead: dict) -> str:
    tags = ", ".join(str(tag) for tag in (lead.get("tags") or [])[:4]) or "none"
    return (
        f"- Lead #{lead.get('id')}: {lead.get('username', 'unknown')} | "
        f"platform={lead.get('platform', 'unknown')} | followers={lead.get('followers', 0)} | "
        f"email={lead.get('email') or 'none'} | tags={tags}"
    )


def _fallback_marketing_action(action: str, leads: list[dict], product_context: str, language: str) -> str:
    lead = leads[0]
    scoring_lines = []
    for item in leads:
        scoring = score_lead(item)
        scoring_lines.append(
            f"- **{item.get('username', 'Unknown lead')}**: {scoring['score']}/10, tier {scoring['tier']}. "
            f"Breakdown: {scoring['breakdown']}. "
            f"Next step: {'abandon; do not develop' if scoring['tier'] == 'C' else 'ask about lead time or available stock after confirming project fit'}."
        )
    if action == "classify":
        heading = "## 潜在客户评分" if language == "zh" else "## Lead Scoring"
        return heading + "\n\n" + "\n".join(scoring_lines)

    scoring = score_lead(lead)
    if scoring["tier"] == "C":
        return "## Lead skipped\n\nThis lead is C-tier under scoring_rules.md or disqualified by target_market.md. Do not develop."

    username_clean = str(lead.get("username") or "there").strip().lstrip("@")
    research = {
        "industry": product_context.strip() or "current project",
        "interests": [product_context.strip() or "current project"],
    }
    signal = first_specific_signal(lead, research)
    if action == "email":
        return f"""## Personalized Cold Email

**Subject:** {subject_for_signal(signal)}

{initial_email_body(lead, research, product_context)}
"""

    return f"""## Social Outreach

**LinkedIn DM**
Hi {username_clean}, I saw your work on {signal}. Before discussing price, should I check lead time or available stock for your current project?

**X / Twitter DM**
Hi {username_clean}, I saw your work on {signal}. Should I check lead time or available stock for your current project?

**Follow-up SOP**
Day 3: follow up once. Day 7: send a relevant case only if available from supplied materials. Day 14: ask project progress. After 30 days without reply: downgrade to C.
"""
    username = lead.get("username") or "您好"
    niche = product_context.strip() or ((lead.get("tags") or ["跨境电商"])[0])
    if language == "zh":
        if action == "email":
            return f"""## 个性化开发信

**建议主题：** 关于 {niche} 的合作机会

您好，{username}：

关注到您在 {lead.get("platform", "社交平台")} 上持续分享与 **{niche}** 相关的内容。我们正在为该领域的品牌和渠道伙伴提供更高效的获客与转化支持，希望了解您当前在客户增长或市场拓展方面的重点。

如果您方便，我可以根据您的业务场景整理一份简短建议。是否可以安排一次 15 分钟沟通？

祝好"""
        if action == "classify":
            lines = ["## 潜在客户评分", ""]
            for item in leads:
                followers = item.get("followers", 0)
                score = min(95, 45 + (20 if followers >= 10_000 else 10 if followers >= 1_000 else 0) + (10 if item.get("email") else 0))
                tier = "高意向" if score >= 75 else "中意向" if score >= 55 else "待培育"
                evidence = "已有公开邮箱，可优先邮件触达" if item.get("email") else f"可从 {item.get('platform', '社交平台')} 私信开始建立联系"
                lines.append(f"- **{item.get('username', '未知客户')}**：{score}/100，{tier}。判断依据：{evidence}。下一步：围绕 {niche} 的业务价值发送一条简短、个性化的首次消息。")
            return "\n".join(lines)
        return f"""## 社交媒体跟进建议

**LinkedIn 私信**
您好，{username}。关注到您在 {niche} 领域的内容，很有启发。我们正在帮助相关团队提升获客效率，希望有机会交流您目前最关注的增长问题。

**X / Twitter 私信**
Hi {username}，看到您分享的 {niche} 内容，很有启发。我们在帮助相关品牌优化获客与转化，方便交流一下您当前最关注的增长方向吗？

**跟进建议**
首次触达保持简短；若 3 天内未回复，可补充一条与其公开内容相关的具体观察。"""
    if action == "email":
        return f"""## Personalized Cold Email

**Subject:** Exploring a {niche} growth opportunity

Hi {username},

I noticed your work around **{niche}** on {lead.get("platform", "social media")}. We help teams in this space improve lead generation and conversion, and I would be interested in learning which growth priorities matter most to you right now.

Would you be open to a brief 15-minute conversation next week?

Best regards"""
    if action == "classify":
        lines = ["## Lead Scoring", ""]
        for item in leads:
            followers = item.get("followers", 0)
            score = min(95, 45 + (20 if followers >= 10_000 else 10 if followers >= 1_000 else 0) + (10 if item.get("email") else 0))
            tier = "High intent" if score >= 75 else "Medium intent" if score >= 55 else "Nurture"
            evidence = "public email is available" if item.get("email") else f"start with a {item.get('platform', 'social')} DM"
            lines.append(f"- **{item.get('username', 'Unknown lead')}**: {score}/100, {tier}. Evidence: {evidence}. Next step: send a concise, personalized message focused on the business value of {niche}.")
        return "\n".join(lines)
    return f"""## Social Follow-up Suggestions

**LinkedIn DM**
Hi {username}, I enjoyed your perspective on {niche}. We help teams in this space improve lead generation and conversion. Would you be open to comparing notes on your current growth priorities?

**X / Twitter DM**
Hi {username}, enjoyed your posts on {niche}. We work with teams improving acquisition and conversion. Open to a quick exchange on what you are prioritizing this quarter?

**Follow-up**
Keep the first message brief. If there is no reply after three days, follow up with one specific observation from their public profile."""


def _marketing_action_prompt(action: str, leads: list[dict], product_context: str, language: str) -> tuple[str, str]:
    action_guidance = {
        "email": "Write one personalized cold email with a subject line, concise body, and a CTA about lead time or available stock.",
        "classify": "Score each lead from 0-10 using scoring_rules.md, assign S/A/B/C, explain the evidence, and recommend abandon for C-tier leads.",
        "social": "Write one LinkedIn DM, one X/Twitter DM under 240 characters, and the follow-up SOP.",
    }[action]
    language_rule = "Write in Simplified Chinese." if language == "zh" else "Write in English."
    system = (
        "You are a senior B2B growth marketer for cross-border e-commerce. "
        "Use only these five files as the business standard: product_brief.md says main product is '用户填写' and core advantage is '用户填写'; "
        "target_market.md targets Europe and North America, prioritizes engineering distributors, lighting contractors, renovation companies, and forbids retailers, trading middlemen, and price-only contacts; "
        "scoring_rules.md uses S=8-10, A=5-7, B=3-4, C=<3 abandon; "
        "email_style.md requires a direct professional tone, first sentence mentioning the customer's specific project or product, no upfront quote, an ending about lead time or available stock, and never 'hope this email finds you well'; "
        "follow_up_sop.md requires day 3 follow-up, day 7 case, day 14 project progress, and C downgrade after 30 days without reply. "
        "Produce concise, specific, ready-to-use copy. Never invent names, companies, referrals, events, private facts, products, prices, cases, or capabilities. "
        "Use only the supplied lead data. Avoid hype, placeholders, and generic filler. Do not develop C-tier or disqualified leads. "
        f"{language_rule} Return clean Markdown only."
    )
    user = f"""Task: {action_guidance}

Product or niche context: {product_context or "not provided"}

Owned lead data:
{chr(10).join(_lead_summary(lead) for lead in leads)}

Quality requirements:
- Mention only facts present in the lead data.
- Keep the output scannable with headings and bullets where appropriate.
- Do not include analysis notes or unsupported claims."""
    return system, user


# ========================
# LLM Test Endpoint
# ========================

@router.post("/test-llm")
async def test_llm(request: ChatRequest, current_user=Depends(get_current_user)):
    """Test LLM connectivity via OpenRouter"""
    # 检查 API Key 是否配置
    if not API_KEY or API_KEY == "sk-or-v1-your-key-here":
        return {
            "status": "error",
            "message": "OpenRouter API key not configured. Please set OPENROUTER_API_KEY in .env file. Get your key at https://openrouter.ai/keys"
        }

    try:
        client = _get_llm_client()

        lang = request.language if request.language in ("zh", "en") else "en"
        system_prompt = (
            "You are a helpful assistant for cross-border e-commerce. "
            "Always respond in the same language as the user's message. "
            "Use clean plain text or markdown formatting. "
            "Do NOT translate the user's input into another language."
        )

        response = await client.chat.completions.create(
            model="meta-llama/llama-3-8b-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt}
            ],
            extra_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "OpenClaw AI Agent",
            }
        )
        return {"status": "success", "reply": response.choices[0].message.content}
    except Exception as e:
        error_str = str(e)
        # 提供更友好的错误提示
        if "401" in error_str or "authentication" in error_str.lower():
            return {
                "status": "error",
                "message": f"OpenRouter authentication failed. Please check your API key at https://openrouter.ai/keys. Error: {error_str}"
            }
        elif "connection" in error_str.lower() or "timeout" in error_str.lower():
            return {
                "status": "error",
                "message": f"Failed to connect to OpenRouter. Please check your internet connection. Error: {error_str}"
            }
        else:
            return {"status": "error", "message": f"OpenRouter API call failed: {error_str}"}


@router.post("/marketing-action")
async def marketing_action(
    request: MarketingActionRequest,
    current_user=Depends(get_current_user),
):
    """Generate validated, ready-to-use output for one marketing action."""
    from db import get_db_pool as _get_pool

    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, platform, username, profile_url, email, followers, tags
               FROM leads
               WHERE user_id = $1 AND id = ANY($2::int[])
               ORDER BY created_at DESC""",
            current_user.id, request.lead_ids,
        )
    leads = [dict(row) for row in rows]
    if not leads:
        raise HTTPException(status_code=404, detail="No owned leads found")

    fallback = _fallback_marketing_action(
        request.action, leads, request.product_context, request.language
    )
    if not API_KEY or API_KEY == "sk-or-v1-your-key-here":
        return {"status": "success", "content": fallback, "generation_mode": "local_fallback"}

    try:
        system_prompt, user_prompt = _marketing_action_prompt(
            request.action, leads, request.product_context, request.language
        )
        client = _get_llm_client()
        response, model_used = await _create_marketing_completion(
            client,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.35,
            max_tokens=1400,
        )
        content = (response.choices[0].message.content or "").strip()
        if not _is_usable_marketing_text(content, request.language):
            return {"status": "success", "content": fallback, "generation_mode": "quality_fallback"}
        return {"status": "success", "content": content, "generation_mode": "openrouter", "model": model_used}
    except Exception as exc:
        print(f"[MarketingAction] Falling back to local output: {exc}")
        return {"status": "success", "content": fallback, "generation_mode": "error_fallback"}


# ========================
# Agent List
# ========================

@router.get("/")
async def get_agents(current_user=Depends(get_current_user)):
    """List all available agents"""
    return {
        "agents": [
            {"name": "LeadAgent", "status": "operational", "platforms": ["twitter", "x", "linkedin", "tiktok", "facebook", "instagram", "shopify"]},
            {"name": "LinkedInAgent", "status": "placeholder", "platforms": ["linkedin"]},
            {"name": "FacebookAgent", "status": "placeholder", "platforms": ["facebook"]},
            {"name": "TwitterAgent", "status": "placeholder", "platforms": ["twitter", "x"]},
            {"name": "TikTokAgent", "status": "operational", "platforms": ["tiktok"]},
            {"name": "EmailAgent", "status": "placeholder", "platforms": ["email"]},
            {"name": "CommentAgent", "status": "placeholder", "platforms": ["twitter", "linkedin", "facebook"]},
            {"name": "MarketingAgent", "status": "placeholder", "platforms": ["all"]},
            {"name": "ReportAgent", "status": "placeholder", "platforms": ["all"]},
            {"name": "DataAgent", "status": "placeholder", "platforms": ["all"]},
            {"name": "ShopifyAgent", "status": "placeholder", "platforms": ["shopify"]},
            {"name": "AdsAgent", "status": "placeholder", "platforms": ["facebook", "google"]},
        ]
    }


# ========================
# Pool Status
# ========================

@router.get("/pool-status")
async def get_pool_status(current_user=Depends(get_current_user)):
    """Get browser pool status"""
    try:
        pool = get_browser_pool()
        status = await pool.get_pool_status()
        return {"status": "success", "pool": status}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ========================
# Queue Status
# ========================

@router.get("/queue-status")
async def get_queue_status(current_user=Depends(get_current_user)):
    """Get task queue status"""
    try:
        queue = get_task_queue()
        status = await queue.get_status()
        return {"status": "success", "queue": status}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ========================
# Task Submit (Async via Queue)
# ========================

@router.post("/submit-task")
async def submit_task(
    request: TaskSubmitRequest,
    current_user=Depends(get_current_user)
):
    """
    Submit a task to the queue for async execution.
    Creates a database record and enqueues for immediate execution.
    """
    import json

    valid_agents = [
        "LeadAgent", "LinkedInAgent", "FacebookAgent",
        "TwitterAgent", "EmailAgent", "CommentAgent",
        "MarketingAgent", "ReportAgent", "DataAgent",
        "HarnessAgent"
    ]

    if request.agent_name not in valid_agents:
        raise HTTPException(status_code=400, detail=f"Invalid agent: {request.agent_name}")

    try:
        from db import get_db_pool as _get_pool
        pool = await _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO tasks (agent_name, task_type, payload, status, user_id)
                   VALUES ($1, $2, $3, 'pending', $4)
                   RETURNING id""",
                request.agent_name, request.task_type, json.dumps(request.payload), current_user.id
            )

        task_db_id = row['id']
        queue = get_task_queue()
        await queue.submit_task(
            task_id=task_db_id,
            user_id=current_user.id,
            agent_name=request.agent_name,
            task_type=request.task_type,
            payload=request.payload,
            priority=TaskPriority(request.priority),
            platform=request.platform
        )

        return {
            "status": "queued",
            "message": f"Task queued for {request.agent_name}",
            "task_id": task_db_id,
            "note": "Task will be executed asynchronously. Use /api/tasks/{id} to check status."
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")


# ========================
# Scrape Test (with Browser Pool)
# ========================

def _match_geography(lead: dict, geo: str) -> bool:
    """根据地区过滤线索"""
    # 地区映射：关键词匹配
    geo_keywords = {
        "us": ["usa", "united states", "america", "us ", " u.s."],
        "uk": ["uk", "united kingdom", "britain", "london"],
        "ca": ["canada", "toronto", "vancouver"],
        "au": ["australia", "sydney", "melbourne"],
        "de": ["germany", "deutschland", "berlin"],
        "fr": ["france", "paris", "français"],
        "jp": ["japan", "tokyo", "日本語"],
        "sg": ["singapore", "sg", "singaporean"],
    }
    geo_tags = lead.get("tags", [])
    username = lead.get("username", "").lower()
    profile_url = lead.get("profile_url", "").lower()

    if geo not in geo_keywords:
        return True

    keywords = geo_keywords[geo]
    for tag in geo_tags:
        tag_lower = tag.lower()
        for kw in keywords:
            if kw in tag_lower:
                return True
    for kw in keywords:
        if kw in username or kw in profile_url:
            return True
    return False


def _match_follower_range(lead: dict, follower_range: str) -> bool:
    """根据粉丝规模过滤线索"""
    followers = lead.get("followers", 0)
    range_map = {
        "0-1k": (0, 1000),
        "1k-10k": (1000, 10000),
        "10k-50k": (10000, 50000),
        "50k-100k": (50000, 100000),
        "100k+": (100000, float("inf")),
    }
    if follower_range not in range_map:
        return True
    low, high = range_map[follower_range]
    return low <= followers < high


def _match_content_type(lead: dict, content_type: str) -> bool:
    """根据账号类型过滤线索"""
    if content_type == "all":
        return True
    tags = [t.lower() for t in lead.get("tags", [])]
    if content_type == "influencer":
        return any(t in tags for t in ["influencer", "kOL", "creator", "verified", "expert"])
    elif content_type == "business":
        return any(t in tags for t in ["business", "company", "brand", "store", "shop"])
    elif content_type == "creator":
        return any(t in tags for t in ["creator", "content", "youtuber", "streamer"])
    elif content_type == "reseller":
        return any(t in tags for t in ["reseller", "wholesale", "dropship", "supplier"])
    return True


async def _scrape_tiktok(page, keyword: str) -> list:
    """Scrape TikTok for user profiles matching keyword"""
    import urllib.parse
    leads = []
    encoded_keyword = urllib.parse.quote(keyword)

    try:
        url = f"https://www.tiktok.com/search/user?keyword={encoded_keyword}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # Wait for results
        try:
            await page.wait_for_selector('[data-e2e="search-user-item"]', timeout=8000)
        except Exception:
            print("[API] TikTok: waiting for results timeout")

        # Extract user cards
        user_cells = await page.query_selector_all('[data-e2e="search-user-item"]')
        for cell in user_cells[:20]:
            try:
                username_elem = await cell.query_selector('a')
                name_elem = await cell.query_selector('[data-e2e="search-user-name"]')

                username = await username_elem.text_content() if username_elem else ""
                href = await username_elem.get_attribute('href') if username_elem else ""
                name = await name_elem.text_content() if name_elem else ""

                if username and href:
                    profile_url = href if href.startswith('http') else f"https://www.tiktok.com{href}"
                    username = username.strip().replace('@', '')

                    leads.append({
                        "platform": "tiktok",
                        "username": username or name,
                        "profile_url": profile_url,
                        "email": None,
                        "followers": 0,
                        "tags": [keyword, "tiktok"]
                    })
            except Exception:
                continue

        print(f"[API] TikTok: extracted {len(leads)} users")

    except Exception as e:
        print(f"[API] TikTok: error: {e}")

    return leads


async def _scrape_facebook(page, keyword: str) -> list:
    """Scrape Facebook for pages/groups matching keyword"""
    import urllib.parse
    leads = []
    encoded_keyword = urllib.parse.quote(keyword)

    try:
        # Search for pages
        url = f"https://www.facebook.com/search/pages?q={encoded_keyword}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # Try to wait for results
        try:
            await page.wait_for_selector('[role="article"]', timeout=8000)
        except Exception:
            print("[API] Facebook: waiting for results timeout")

        # Extract page cards
        articles = await page.query_selector_all('[role="article"]')
        for article in articles[:20]:
            try:
                link_elem = await article.query_selector('a')
                name_elem = await article.query_selector('span')

                name = await name_elem.text_content() if name_elem else ""
                href = await link_elem.get_attribute('href') if link_elem else ""

                if name and href:
                    profile_url = href if href.startswith('http') else f"https://www.facebook.com{href}"

                    leads.append({
                        "platform": "facebook",
                        "username": name.strip(),
                        "profile_url": profile_url,
                        "email": None,
                        "followers": 0,
                        "tags": [keyword, "facebook", "page"]
                    })
            except Exception:
                continue

        print(f"[API] Facebook: extracted {len(leads)} pages")

    except Exception as e:
        print(f"[API] Facebook: error: {e}")

    return leads


async def _scrape_twitter(page, keyword: str) -> list:
    """Scrape Twitter/X for user profiles matching keyword"""
    import urllib.parse
    import re
    leads = []
    encoded_keyword = urllib.parse.quote(keyword)

    # Search user accounts by the keyword. Prefixing "@" only works for exact handles
    # and makes normal niche keywords like "led light" return poor or empty results.
    url = f"https://x.com/search?q={encoded_keyword}&src=typed_query&f=user"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    # 等待页面加载
    await asyncio.sleep(3)

    # 检测登录墙
    current_url = page.url
    if "login" in current_url or "i/flow/login" in current_url:
        print("[API] Twitter: login wall detected — search requires authentication")
        return []

    # 向下滚动几次加载更多真实用户
    for _ in range(3):
        await page.evaluate("window.scrollBy(0, 800)")
        await asyncio.sleep(1)

    # Wait for user cells with retry
    for attempt in range(2):
        try:
            await page.wait_for_selector('[data-testid="UserCell"]', timeout=6000)
            break
        except Exception:
            # Try scrolling to load more content
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(1)

    user_cells = await page.query_selector_all('[data-testid="UserCell"]')
    print(f"[API] Twitter: found {len(user_cells)} user cells")

    for cell in user_cells[:20]:
        try:
            # 获取所有文本内容进行调试
            all_texts = await cell.query_selector_all('span')
            text_contents = [await t.text_content() for t in all_texts if await t.text_content()]
            print(f"[API] Twitter cell texts: {text_contents[:5]}")

            # 查找 handle - 通常格式是 @username
            handle = ""
            name = ""

            for text in text_contents:
                text = text.strip()
                # 匹配 Twitter handle 格式
                if re.match(r'^@?[a-zA-Z0-9_]{1,15}$', text) and not text.startswith('@'):
                    # 这可能是用户名（不带@的）
                    if not handle:
                        handle = f"@{text}"
                elif text.startswith('@') and len(text) > 1:
                    handle = text
                    break

            # 查找显示名称（通常是比较长的文本）
            for text in text_contents:
                text = text.strip()
                if text and not text.startswith('@') and len(text) > 2 and len(text) < 50:
                    # 排除数字和短文本
                    if not re.match(r'^[0-9,]+$', text):
                        name = text
                        break

            # 验证 handle 格式
            if handle:
                clean_handle = handle.strip('@')
                # 验证是有效的 Twitter handle
                if re.match(r'^[a-zA-Z0-9_]{1,15}$', clean_handle):
                    profile_url = f"https://x.com/{clean_handle}"

                    # 提取粉丝数（如果能找到）
                    followers = 0
                    for text in text_contents:
                        parsed_followers = _parse_social_count(text)
                        if parsed_followers:
                            followers = parsed_followers
                            break

                    source_text = " ".join(text_contents[:12])
                    if not _matches_keyword_intent(source_text, keyword):
                        print(f"[API] Twitter: skipped irrelevant profile @{clean_handle}, keyword={keyword!r}")
                        continue
                    metadata = _extract_asset_metadata(source_text, profile_url, name)
                    if source_text:
                        metadata["summary"] = source_text[:500]
                        metadata["source_evidence"] = source_text[:500]
                    metadata["lead_source"] = "x_people_search"
                    candidate = {
                        "platform": "x",
                        "username": f"{name} ({handle})" if name else handle,
                        "profile_url": profile_url,
                        "email": None,
                        "followers": followers,
                        "tags": [keyword],
                        "metadata": metadata,
                    }
                    if _is_low_value_social_lead(candidate, keyword):
                        print(f"[API] Twitter: skipped low-value social profile @{clean_handle}, name={name}")
                        continue
                    leads.append(candidate)
                    print(f"[API] Twitter: extracted @{clean_handle}, name={name}, followers={followers}")
        except Exception as e:
            print(f"[API] Twitter parse error: {e}")
            continue

    return leads


async def _scrape_linkedin(page, keyword: str) -> list:
    """Scrape LinkedIn for user profiles matching keyword"""
    import urllib.parse
    leads = []
    seen_urls = set()

    # LinkedIn search URL
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_keyword}&origin=GLOBAL_SEARCH_HEADER"

    await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    # Wait and check for login wall
    await asyncio.sleep(3)

    # Check if redirected to login or checkpoint
    if "login" in page.url.lower() or "checkpoint" in page.url.lower():
        print(f"[API] LinkedIn requires login/checkpoint, url={page.url}")
        return []

    # Current LinkedIn UI lazy-loads search rows; scroll before extraction.
    for _ in range(3):
        try:
            await page.evaluate("window.scrollBy(0, 900)")
            await asyncio.sleep(1)
        except Exception:
            break

    # Try multiple selectors for LinkedIn search results
    selectors = [
        '.entity-result',
        '.search-result__occluded-item',
        '[data-test-id="people-search-result"]',
        '.reusable-search__result-container'
    ]

    user_cards = []
    for selector in selectors:
        user_cards = await page.query_selector_all(selector)
        if user_cards:
            print(f"[API] LinkedIn: found {len(user_cards)} cards with selector {selector}")
            break

    for card in user_cards[:30]:
        try:
            # Extract name - multiple selectors
            name = ""
            for name_sel in ['.entity-result__title-text a', '.search-result__info a', '[data-test-id="people-search-name"]']:
                name_el = await card.query_selector(name_sel)
                if name_el:
                    name = await name_el.text_content()
                    break

            # Extract title/subtitle
            title = ""
            for title_sel in ['.entity-result__primary-subtitle', '.search-result__snippet']:
                title_el = await card.query_selector(title_sel)
                if title_el:
                    title = await title_el.text_content()
                    break

            # Extract profile URL
            profile_url = ""
            for link_sel in ['.entity-result__title-text a', '.search-result__info a']:
                link_el = await card.query_selector(link_sel)
                if link_el:
                    profile_url = await link_el.get_attribute('href')
                    break

            if profile_url and not profile_url.startswith('http'):
                profile_url = 'https://www.linkedin.com' + profile_url
            if profile_url:
                profile_url = profile_url.split("?", 1)[0].rstrip("/")
            if profile_url in seen_urls:
                continue

            if name:
                seen_urls.add(profile_url)
                card_text = await card.text_content() or ""
                metadata = _extract_asset_metadata(card_text, profile_url, name.strip())
                if title and not metadata.get("title"):
                    metadata["title"] = title.strip()
                leads.append({
                    "platform": "linkedin",
                    "username": name.strip(),
                    "profile_url": profile_url,
                    "email": _first_public_email(card_text),
                    "followers": 0,
                    "tags": [keyword],
                    "metadata": metadata
                })
        except Exception as e:
            print(f"[API] LinkedIn parse error: {e}")
            continue

    if leads:
        print(f"[API] LinkedIn: extracted {len(leads)} leads from card selectors")
        return leads

    # Fallback for newer localized LinkedIn markup: result cards may not expose stable
    # class names, but profile links remain anchored under /in/.
    profile_links = await page.query_selector_all('a[href*="/in/"]')
    print(f"[API] LinkedIn: card selectors empty, found {len(profile_links)} profile links")
    for link in profile_links[:80]:
        try:
            href = await link.get_attribute("href")
            if not href:
                continue
            profile_url = href if href.startswith("http") else f"https://www.linkedin.com{href}"
            profile_url = profile_url.split("?", 1)[0].rstrip("/")
            if "/in/" not in profile_url or profile_url in seen_urls:
                continue

            link_text = (await link.text_content() or "").strip()
            card_text = await link.evaluate(
                """el => {
                    const card = el.closest('li') || el.closest('[data-view-name]') || el.closest('div');
                    return (card && card.innerText) || el.innerText || '';
                }"""
            )
            lines = [line.strip() for line in re.split(r"[\r\n]+", card_text or "") if line.strip()]
            name = link_text or (lines[0] if lines else "")
            name = re.split(r"\s+•\s+", name, 1)[0].strip()
            if not name or name.casefold() in {"linkedin", "查看资料", "view profile"}:
                continue

            title = ""
            if lines:
                for line in lines[1:5]:
                    if line and not any(skip in line for skip in ("加为好友", "关注", "Connect", "Follow")):
                        title = line
                        break

            metadata = _extract_asset_metadata(card_text or "", profile_url, name)
            if title and not metadata.get("title"):
                metadata["title"] = title
            seen_urls.add(profile_url)
            leads.append({
                "platform": "linkedin",
                "username": name,
                "profile_url": profile_url,
                "email": _first_public_email(card_text or ""),
                "followers": 0,
                "tags": [keyword, "linkedin"],
                "metadata": metadata,
            })
        except Exception as e:
            print(f"[API] LinkedIn link fallback parse error: {e}")
            continue

    # Some LinkedIn results are privacy-masked as "LinkedIn Member/领英会员" and
    # do not expose /in/ links, but their result rows still contain useful
    # headline, company, and country data.
    result_texts = await page.evaluate(
        """() => Array.from(document.querySelectorAll('main [role="listitem"]'))
            .map(el => el.innerText || el.textContent || '')
            .filter(Boolean)"""
    )
    print(f"[API] LinkedIn: found {len(result_texts)} list item texts for text fallback")
    seen_names = {str(lead.get("username") or "").casefold() for lead in leads}
    for item_text in result_texts[:30]:
        try:
            item_text = str(item_text or "").strip()
            lines = [line.strip() for line in re.split(r"[\r\n]+", item_text) if line.strip()]
            if len(lines) < 2:
                continue
            if any(marker in item_text for marker in ("这些结果有用吗", "您的反馈", "下一步", "Previous", "Next")):
                continue
            lowered_item_text = item_text.casefold()
            search_terms = [term for term in re.split(r"\s+", keyword.casefold()) if term]
            if search_terms and not any(term in lowered_item_text for term in search_terms):
                continue

            first_line = lines[0]
            is_masked_member = first_line in {"领英会员", "LinkedIn Member"}
            if is_masked_member and len(lines) > 1:
                headline = lines[1]
                username = f"{first_line} - {headline[:80]}"
            else:
                username = re.split(r"\s+•\s+", first_line, 1)[0].strip()
                headline = lines[1] if len(lines) > 1 else ""
            if not username or username.casefold() in seen_names:
                continue

            company = ""
            country = ""
            for line in lines:
                if line.startswith("目前就职:") or line.startswith("Current:"):
                    company_part = re.sub(r"^(目前就职:|Current:)\s*", "", line).strip()
                    company = company_part.split(" - ", 1)[0].strip()
                if line.startswith("中国") or line in {"United States", "United Kingdom", "Canada", "Australia", "Germany", "France", "Japan", "Singapore"}:
                    country = line

            metadata = _extract_asset_metadata(item_text, "", username)
            if is_masked_member:
                metadata["title"] = headline
                metadata["company_name"] = company or headline
            elif headline and not metadata.get("title"):
                metadata["title"] = headline
            if company and not metadata.get("company"):
                metadata["company"] = company
            if country and not metadata.get("country"):
                metadata["country"] = country
            seen_names.add(username.casefold())
            leads.append({
                "platform": "linkedin",
                "username": username,
                "profile_url": "",
                "email": _first_public_email(item_text),
                "followers": 0,
                "tags": [keyword, "linkedin", "linkedin_text_result"],
                "metadata": metadata,
            })
        except Exception as e:
            print(f"[API] LinkedIn text fallback parse error: {e}")
            continue

    print(f"[API] LinkedIn: extracted {len(leads)} leads via fallbacks")

    return leads


async def _scrape_instagram(page, keyword: str) -> list:
    """Scrape Instagram for hashtags and user profiles matching keyword"""
    import urllib.parse
    leads = []

    # Instagram hashtag search
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://www.instagram.com/explore/tags/{encoded_keyword}/"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    await asyncio.sleep(3)

    # Check for login wall
    if "login" in page.url or "checkpoint" in page.url.lower():
        print("[API] Instagram requires login")
        return []

    # Try to find post links
    post_links = await page.query_selector_all('a[href*="/p/"]')
    for link in post_links[:10]:
        try:
            href = await link.get_attribute('href')
            if href and '/p/' in href:
                leads.append({
                    "platform": "instagram",
                    "username": f"instagram_post_{keyword}",
                    "profile_url": f"https://www.instagram.com{href}",
                    "email": None,
                    "followers": 0,
                    "tags": [keyword]
                })
        except Exception:
            continue

    return leads[:10]


async def _scrape_shopify(page, keyword: str, store_domain: str = None) -> list:
    """Scrape Shopify stores for products matching keyword"""
    import urllib.parse
    leads = []

    # If specific store domain provided, scrape that store directly
    if store_domain:
        if not store_domain.startswith('http'):
            store_domain = f"https://{store_domain}"
        url = f"{store_domain}/search?q={urllib.parse.quote(keyword)}"
    else:
        # Try Shopify's store directory (may be blocked by Cloudflare)
        encoded_keyword = urllib.parse.quote(keyword)
        url = f"https://www.shopify.com/search?q={encoded_keyword}"

    print(f"[API] Shopify: navigating to {url}")
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"[API] Shopify: response status = {response.status}, url = {page.url}")

        await asyncio.sleep(3)

        # Check for Cloudflare or login redirect
        if response.status in [403, 429] or "challenge" in page.url.lower():
            print(f"[API] Shopify: blocked by Cloudflare/protection (status {response.status})")
            # Try to extract any visible links
            page_content = await page.content()
            if "Cloudflare" in page_content:
                return []
            # Fall through to try other selectors

        # Get page content for debugging
        title = await page.title()
        print(f"[API] Shopify: page title = {title}")

        # Try multiple selectors for product results
        product_selectors = [
            '[data-testid="product-card"]',
            '.product-card',
            '.search-results__product',
            'a[href*="/products/"]',
            '.product-item',
            '.grid__item',
            '.product-item__info'
        ]

        products = []
        for selector in product_selectors:
            found = await page.query_selector_all(selector)
            if found:
                print(f"[API] Shopify: found {len(found)} products with selector: {selector}")
                products = found
                break

        if not products:
            # Try to get any links to products
            all_links = await page.query_selector_all('a[href*="/products/"]')
            print(f"[API] Shopify: found {len(all_links)} product links")

            for link in all_links[:15]:
                try:
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    if href and '/products/' in href:
                        full_url = href if href.startswith('http') else f'https://shopify.com{href}'
                        leads.append({
                            "platform": "shopify",
                            "username": text.strip() if text else keyword,
                            "profile_url": full_url,
                            "email": None,
                            "followers": 0,
                            "tags": [keyword, "product"]
                        })
                except Exception:
                    continue
        else:
            for product in products[:15]:
                try:
                    # Extract product name
                    name = ""
                    for name_sel in ['h2', '.product-card__title', '[data-testid="product-title"]', '.product-item__title', '.product-title']:
                        name_el = await product.query_selector(name_sel)
                        if name_el:
                            name = await name_el.text_content()
                            break

                    # Extract product URL
                    product_url = ""
                    link_el = await product.query_selector('a[href*="/products/"]')
                    if not link_el:
                        link_el = await product.query_selector('a')
                    if link_el:
                        product_url = await link_el.get_attribute('href')
                    if product_url and not product_url.startswith('http'):
                        product_url = 'https://shopify.com' + product_url

                    if name:
                        leads.append({
                            "platform": "shopify",
                            "username": name.strip(),
                            "profile_url": product_url,
                            "email": None,
                            "followers": 0,
                            "tags": [keyword, "product"]
                        })
                except Exception as e:
                    print(f"[API] Shopify parse error: {e}")
                    continue

        print(f"[API] Shopify: extracted {len(leads)} leads")

    except Exception as e:
        print(f"[API] Shopify: navigation error: {e}")

    return leads


async def _scrape_google(page, keyword: str, suffix: str = "company") -> list:
    """Scrape Google search results for websites/companies matching keyword"""
    import urllib.parse
    from urllib.parse import urlparse
    leads = []

    # Google search URL
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://www.google.com/search?q={encoded_keyword}+{urllib.parse.quote(suffix)}&num=30" if suffix else f"https://www.google.com/search?q={encoded_keyword}&num=30"

    print(f"[API] Google: navigating to {url}")
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"[API] Google: response status = {response.status}, url = {page.url}")

        await asyncio.sleep(3)

        # Handle consent/cookie page (common in EU)
        try:
            consent_btn = await page.query_selector('button:has-text("Accept all"), button:has-text("Reject all"), button:has-text("I agree")')
            if consent_btn:
                await consent_btn.click()
                await asyncio.sleep(2)
        except Exception:
            pass

        # Check for robots/CAPTCHA check
        current_url = page.url.lower()
        page_text = (await page.content()).lower()
        if "sorry" in current_url or "search1972" in current_url or "captcha" in page_text or "unusual traffic" in page_text:
            print("[API] Google: blocked by CAPTCHA/robots check")
            return []

        # Extract search results — try multiple selectors
        results = []
        for selector in ['div.g', 'div[data-sokoban-container]', 'div.tF2Cxc', '.MjjYud']:
            results = await page.query_selector_all(selector)
            if results:
                print(f"[API] Google: found {len(results)} results with selector '{selector}'")
                break

        if not results:
            # Fallback: get all h3 elements (each is a search result title)
            h3s = await page.query_selector_all('h3')
            print(f"[API] Google: fallback found {len(h3s)} h3 elements")
            for h3 in h3s[:30]:
                try:
                    title = await h3.text_content()
                    # Walk up to find the parent <a> tag
                    link_el = await h3.evaluate_handle('el => el.closest("a")')
                    if link_el:
                        href = await link_el.get_attribute('href')
                        if title and href and href.startswith('http'):
                            domain = urlparse(href).netloc
                            snippet = await h3.evaluate('el => el.closest("div")?.innerText || el.innerText || ""')
                            leads.append({
                                "platform": "google",
                                "username": title.strip(),
                                "profile_url": href,
                                "email": _first_public_email(snippet or ""),
                                "followers": 0,
                                "tags": [keyword, domain],
                                "metadata": _extract_asset_metadata(snippet or "", href, title.strip()),
                            })
                except Exception:
                    continue
            print(f"[API] Google: extracted {len(leads)} results via h3 fallback")
            return leads

        for result in results[:30]:
            try:
                title_el = await result.query_selector('h3')
                link_el = await result.query_selector('a')

                title = await title_el.text_content() if title_el else ""
                href = await link_el.get_attribute('href') if link_el else ""

                if title and href and href.startswith('http'):
                    domain = urlparse(href).netloc
                    snippet = await result.text_content()

                    leads.append({
                        "platform": "google",
                        "username": title.strip(),
                        "profile_url": href,
                        "email": _first_public_email(snippet or ""),
                        "followers": 0,
                        "tags": [keyword, domain],
                        "metadata": _extract_asset_metadata(snippet or "", href, title.strip()),
                    })
            except Exception:
                continue

        print(f"[API] Google: extracted {len(leads)} results")

    except Exception as e:
        print(f"[API] Google: error: {e}")

    return leads


def _social_platform_from_url(url: str) -> str:
    """Recover the requested social platform from a search-result URL."""
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower().split(":", 1)[0].removeprefix("www.")
    domains = {
        "linkedin.com": "linkedin",
        "x.com": "x",
        "twitter.com": "x",
        "facebook.com": "facebook",
        "instagram.com": "instagram",
        "tiktok.com": "tiktok",
    }
    for domain, platform in domains.items():
        if host == domain or host.endswith(f".{domain}"):
            return platform
    return "duckduckgo"


async def _scrape_duckduckgo(page, keyword: str) -> list:
    """Scrape DuckDuckGo search results — more headless-friendly than Google"""
    import urllib.parse
    from urllib.parse import urlparse
    leads = []

    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://html.duckduckgo.com/html/?q={encoded_keyword}"

    print(f"[API] DuckDuckGo: navigating to {url}")
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"[API] DuckDuckGo: response status = {response.status}, url = {page.url}")

        await asyncio.sleep(2)
        page_text = await page.content()
        if _is_search_verification_page(page_text):
            print("[API] DuckDuckGo: verification page detected; skipping search results")
            return []

        # DuckDuckGo HTML version has simple structure
        results = await page.query_selector_all('.result')
        if not results:
            results = await page.query_selector_all('.web-result')
        if not results:
            # Fallback: try result links directly
            results = await page.query_selector_all('.result__a')

        print(f"[API] DuckDuckGo: found {len(results)} result elements")

        for result in results[:30]:
            try:
                # Try to get title and link
                link_el = await result.query_selector('a.result__a, a.result__url, a')
                if not link_el:
                    continue

                title = await link_el.text_content()
                href = await link_el.get_attribute('href')

                if not href:
                    continue

                # DuckDuckGo sometimes uses redirect URLs
                if '/l/?uddg=' in href:
                    import re
                    match = re.search(r'uddg=([^&]+)', href)
                    if match:
                        href = urllib.parse.unquote(match.group(1))

                if title and href and href.startswith('http'):
                    domain = urlparse(href).netloc
                    snippet = await result.text_content()
                    leads.append({
                        "platform": _social_platform_from_url(href),
                        "username": title.strip(),
                        "profile_url": href,
                        "email": _first_public_email(snippet or ""),
                        "followers": 0,
                        "tags": [keyword, domain],
                        "metadata": _extract_asset_metadata(snippet or "", href, title.strip()),
                    })
            except Exception:
                continue

        print(f"[API] DuckDuckGo: extracted {len(leads)} results")

    except Exception as e:
        print(f"[API] DuckDuckGo: error: {e}")

    return leads


async def _scrape_platform_search_fallback(page, keyword: str, platform: str) -> list:
    """Use public search only for profiles on the platform the user selected."""
    domain_queries = {
        "linkedin": f'site:linkedin.com "{keyword}"',
        "x": f'(site:x.com OR site:twitter.com) "{keyword}"',
        "twitter": f'(site:x.com OR site:twitter.com) "{keyword}"',
        "facebook": f'site:facebook.com "{keyword}"',
        "instagram": f'site:instagram.com "{keyword}"',
        "tiktok": f'site:tiktok.com "{keyword}"',
    }
    expected_platforms = {"x", "twitter"} if platform in {"x", "twitter"} else {platform}
    query = domain_queries.get(platform)
    if not query:
        return []
    results = await _scrape_duckduckgo(page, query)
    return [lead for lead in results if lead.get("platform") in expected_platforms]


async def _scrape_public_directory(page, keyword: str) -> list:
    """Scrape public business directories for leads"""
    import urllib.parse
    leads = []

    # Yellow Pages as example
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://www.yellowpages.com/search?search_terms={encoded_keyword}&geo_location_terms=USA"

    print(f"[API] Directory: navigating to {url}")
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"[API] Directory: status {response.status}")

        await asyncio.sleep(2)

        # Extract business listings
        listings = await page.query_selector_all('.result')

        for listing in listings[:15]:
            try:
                name_el = await listing.query_selector('.business-name')
                phone_el = await listing.query_selector('.phone')
                link_el = await listing.query_selector('a')

                name = await name_el.text_content() if name_el else ""
                phone = await phone_el.text_content() if phone_el else ""
                href = await link_el.get_attribute('href') if link_el else ""
                listing_text = await listing.text_content()

                if name:
                    profile_url = href if href.startswith('http') else f'https://www.yellowpages.com{href}'
                    leads.append({
                        "platform": "directory",
                        "username": name.strip(),
                        "profile_url": profile_url,
                        "email": _first_public_email(listing_text or ""),
                        "followers": 0,
                        "tags": [keyword, "business", phone.strip() if phone else ""],
                        "metadata": _extract_asset_metadata(listing_text or "", profile_url, name.strip()),
                    })
            except Exception:
                continue

        print(f"[API] Directory: extracted {len(leads)} listings")

    except Exception as e:
        print(f"[API] Directory: error: {e}")

    return leads


async def _extract_email_from_public_page(page, url: str) -> str | None:
    """Visit a public company page and extract the first visible business email."""
    if not _is_email_lookup_candidate(url):
        return None

    from urllib.parse import urljoin, urlparse

    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=12000)
        if response and response.status >= 400:
            return None
        await page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass

    try:
        content = await page.content()
        email = _first_public_email(content)
        if email:
            return email

        mailto_links = await page.query_selector_all('a[href^="mailto:"]')
        for link in mailto_links:
            href = await link.get_attribute("href")
            email = _first_public_email(href or "")
            if email:
                return email

        base_host = urlparse(page.url or url).netloc.lower().split(":", 1)[0].removeprefix("www.")
        contact_links = await page.query_selector_all(
            'a[href*="contact" i], a[href*="about" i], a[href*="impressum" i], a[href*="support" i]'
        )
        candidates: list[str] = []
        for link in contact_links[:8]:
            href = await link.get_attribute("href")
            if not href:
                continue
            absolute = urljoin(page.url or url, href)
            host = urlparse(absolute).netloc.lower().split(":", 1)[0].removeprefix("www.")
            if host == base_host and absolute not in candidates:
                candidates.append(absolute)

        for candidate in candidates[:3]:
            try:
                response = await page.goto(candidate, wait_until="domcontentloaded", timeout=10000)
                if response and response.status >= 400:
                    continue
                content = await page.content()
                email = _first_public_email(content)
                if email:
                    return email
            except Exception:
                continue
    except Exception as exc:
        print(f"[API] Email enrichment failed for {url}: {exc}")
    return None


async def _discover_email_from_search(page, lead: dict, keyword: str = "") -> str | None:
    """Use public search results to find a likely company site, then extract its email."""
    query = _lead_email_discovery_query(lead, keyword)
    if not query.strip():
        return None

    try:
        results = await _public_search_results(page, query, limit=12)
        candidates = [
            url
            for url, score in sorted(
                ((result["url"], _score_company_site_candidate(result["url"], result.get("title", ""), lead, keyword)) for result in results),
                key=lambda item: item[1],
                reverse=True,
            )
            if score >= 0
        ]

        for candidate in candidates[:3]:
            email = await _extract_email_from_public_page(page, candidate)
            if email:
                return email
    except Exception as exc:
        print(f"[API] Email search discovery failed for {lead.get('username')}: {exc}")
    return None


async def _public_search_results(page, query: str, limit: int = 8) -> list[dict[str, str]]:
    """Return normalized public search results from lightweight search pages."""
    import urllib.parse

    if not query.strip():
        return []
    search_targets = [
        f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
        f"https://www.bing.com/search?q={urllib.parse.quote(query)}",
    ]
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for search_url in search_targets:
        try:
            response = await page.goto(search_url, wait_until="domcontentloaded", timeout=12000)
            if response and response.status >= 400:
                continue
            await asyncio.sleep(0.8)
            content = await page.content()
            if _is_search_verification_page(content):
                continue
            anchors = await page.eval_on_selector_all(
                "a",
                """anchors => anchors.map(a => ({
                    href: a.href || a.getAttribute('href') || '',
                    text: (a.innerText || a.textContent || '').trim()
                }))"""
            )
            for anchor in anchors:
                href = _clean_search_result_url(str(anchor.get("href") or ""))
                title = re.sub(r"\s+", " ", str(anchor.get("text") or "")).strip()
                if not href.startswith(("http://", "https://")):
                    continue
                if href in seen:
                    continue
                host = _host_from_url(href)
                if not host or host in {"r.search.yahoo.com"}:
                    continue
                if "duckduckgo.com/y.js" in href or "/search?" in href and any(engine in host for engine in ("bing.com", "google.com")):
                    continue
                seen.add(href)
                results.append({"url": href, "title": title})
                if len(results) >= limit:
                    return results
        except Exception as exc:
            print(f"[API] Public search failed for query={query!r}: {exc}")
            continue
    return results


async def _discover_company_site_from_search(page, lead: dict, keyword: str = "") -> str | None:
    """Find a likely official company site for a lead through public search results."""
    company = _searchable_company_name(lead, keyword)
    query = f'"{company}" {keyword} official website'.strip() if company else _lead_email_discovery_query(lead, keyword).replace("contact email", "official website")
    if not query.strip():
        return None
    results = await _public_search_results(page, query, limit=12)
    scored = sorted(
        ((result["url"], _score_company_site_candidate(result["url"], result.get("title", ""), lead, keyword)) for result in results),
        key=lambda item: item[1],
        reverse=True,
    )
    for href, score in scored:
        if score >= 0:
            return href
    return None


async def _discover_linkedin_asset_from_search(page, lead: dict, keyword: str = "") -> str | None:
    """Find a likely LinkedIn company or decision-maker URL through public search."""
    company = _searchable_company_name(lead, keyword)
    if not company:
        return None
    query = f'site:linkedin.com/company "{company}"'
    results = await _public_search_results(page, query, limit=10)
    for result in results:
        href = result["url"]
        if re.search(r"https?://(?:[a-z]+\.)?linkedin\.com/(?:company|in)/", href, re.IGNORECASE):
            return href
    return None


def _company_asset_search_queries(keyword: str) -> list[str]:
    keyword = re.sub(r"\s+", " ", str(keyword or "")).strip()
    if not keyword:
        return []
    modifiers = [
        "manufacturer official website",
        "private label manufacturer contact",
        "supplier contact email",
        "wholesale supplier official website",
        "distributor official website",
        "factory exporter contact",
        "brand official store contact",
        "contractor company contact",
        "wholesale company official website",
    ]
    quoted = [f'"{keyword}" {modifier}' for modifier in modifiers]
    broad = [f"{keyword} {modifier}" for modifier in modifiers[:5]]
    return quoted + broad


async def _discover_company_asset_leads(
    page,
    keyword: str,
    existing_hosts: set[str] | None = None,
    source_platform: str = "all",
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Actively discover company websites from a keyword and convert them into asset leads."""
    existing_hosts = existing_hosts or set()
    discovered: list[dict[str, Any]] = []
    seen_hosts = set(existing_hosts)

    for query in _company_asset_search_queries(keyword):
        if len(discovered) >= limit:
            break
        results = await _public_search_results(page, query, limit=20)
        scored = sorted(
            (
                (
                    result,
                    _score_company_site_candidate(
                        result["url"],
                        result.get("title", ""),
                        {"username": keyword, "metadata": {"company_name": result.get("title", "")}},
                        keyword,
                    ),
                )
                for result in results
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        for result, score in scored:
            if len(discovered) >= limit:
                break
            url = result["url"].split("#", 1)[0]
            host = _host_from_url(url)
            if not host or host in seen_hosts or score < 0:
                continue
            seen_hosts.add(host)
            metadata = _extract_asset_metadata("", url, result.get("title", ""))
            page_metadata = await _extract_company_assets_from_public_page(page, url)
            metadata.update({key: value for key, value in page_metadata.items() if value and not metadata.get(key)})
            email = await _extract_email_from_public_page(page, metadata.get("website") or url)
            if email:
                metadata["email"] = email
            linkedin_url = metadata.get("linkedin_url")
            if not linkedin_url:
                linkedin_url = await _discover_linkedin_asset_from_search(
                    page,
                    {"username": metadata.get("company_name") or result.get("title") or keyword, "metadata": metadata},
                    keyword,
                )
                if linkedin_url:
                    metadata["linkedin_url"] = linkedin_url
            company_name = _clean_company_asset_name(metadata.get("company_name") or result.get("title") or host)
            if not company_name:
                company_name = host.split(".", 1)[0].replace("-", " ").title()
            lead = {
                "platform": "directory",
                "username": company_name,
                "profile_url": metadata.get("website") or url,
                "email": email,
                "followers": 0,
                "tags": [keyword, "company_asset", "official_site", host],
                "metadata": {
                    **metadata,
                    "company_name": company_name,
                    "website": metadata.get("website") or url,
                    "domain": host,
                    "asset_source": "keyword_company_search",
                    "source_platform": source_platform,
                    "asset_search_query": query,
                },
            }
            _apply_customer_development_rules(lead)
            discovered.append(lead)
    return discovered


async def _extract_company_assets_from_public_page(page, url: str) -> dict[str, str]:
    """Visit a company page and extract structured business asset hints."""
    if not _is_email_lookup_candidate(url):
        return {}
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=12000)
        if response and response.status >= 400:
            return {}
        await page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    try:
        title = await page.title()
        description = ""
        meta = await page.query_selector('meta[name="description"], meta[property="og:description"]')
        if meta:
            description = await meta.get_attribute("content") or ""
        content = await page.content()
        metadata = _extract_asset_metadata(f"{description} {content}", page.url or url, title)
        contact_links = await page.query_selector_all(
            'a[href*="linkedin.com" i], a[href*="crunchbase.com" i], a[href*="about" i], a[href*="team" i]'
        )
        link_text = []
        for link in contact_links[:12]:
            href = await link.get_attribute("href")
            if href:
                link_text.append(href)
        _merge_metadata({"metadata": metadata}, _extract_asset_metadata(" ".join(link_text), page.url or url, title))
        return metadata
    except Exception as exc:
        print(f"[API] Asset enrichment failed for {url}: {exc}")
    return {}


async def _resolve_public_redirect(page, url: str) -> str:
    """Resolve short links such as t.co into a usable public destination."""
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=8000)
        if response and response.status >= 400:
            return ""
        resolved = page.url or url
        if _is_email_lookup_candidate(resolved) and _is_search_result_host_allowed(resolved):
            return resolved.split("?", 1)[0].rstrip("/")
    except Exception:
        return ""
    return ""


async def _extract_assets_from_social_profile(page, lead: dict) -> dict[str, str]:
    """Extract asset hints from an owned social profile page before using search."""
    profile_url = _social_profile_url(lead)
    if not profile_url or not any(domain in profile_url.lower() for domain in ("x.com/", "twitter.com/", "linkedin.com/")):
        return {}
    metadata: dict[str, str] = {}
    try:
        response = await page.goto(profile_url, wait_until="domcontentloaded", timeout=10000)
        if response and response.status >= 400:
            return {}
        await asyncio.sleep(2)
        body_text = await page.locator("body").inner_text(timeout=3000)
        metadata.update(_extract_asset_metadata(body_text, "", _searchable_company_name(lead)))
        profile_bio = ""
        for selector in ('[data-testid="UserDescription"]', '.text-body-medium', '[data-test-id="profile-description"]'):
            try:
                profile_bio = (await page.locator(selector).first.inner_text(timeout=1000)).strip()
                if profile_bio:
                    break
            except Exception:
                continue
        if profile_bio:
            metadata["summary"] = profile_bio[:1000]
            metadata["profile_evidence"] = profile_bio[:1000]
        metadata["profile_url"] = profile_url
        email = _first_public_email(body_text)
        if email:
            metadata["email"] = email
        anchors = await page.eval_on_selector_all(
            "a",
            """anchors => anchors.map(a => ({
                href: a.href || a.getAttribute('href') || '',
                text: (a.innerText || a.textContent || a.getAttribute('aria-label') || '').trim()
            }))"""
        )
        shortlinks: list[str] = []
        for anchor in anchors[:80]:
            href = anchor.get("href", "")
            candidate = _candidate_url_from_social_anchor(href, anchor.get("text", ""))
            host = _host_from_url(href)
            if candidate:
                metadata.setdefault("website", candidate)
                metadata.setdefault("website_source", "social_profile_link")
                host = _host_from_url(candidate)
                if host:
                    metadata.setdefault("domain", host)
                break
            if href and (host in SOCIAL_SHORTLINK_HOSTS or host.endswith(".t.co")):
                shortlinks.append(href)
        if not metadata.get("website"):
            for shortlink in shortlinks[:3]:
                candidate = await _resolve_public_redirect(page, shortlink)
                if candidate:
                    metadata.setdefault("website", candidate)
                    metadata.setdefault("website_source", "social_profile_redirect")
                    host = _host_from_url(candidate)
                    if host:
                        metadata.setdefault("domain", host)
                    break
        if "linkedin.com" in profile_url.lower():
            metadata.setdefault("linkedin_url", profile_url.split("?", 1)[0].rstrip("/"))
        country = _infer_country(metadata.get("website", ""), body_text)
        if country:
            metadata.setdefault("country", country)
    except Exception as exc:
        print(f"[API] Social profile asset extraction failed for {profile_url}: {exc}")
    return metadata


async def _enrich_leads_with_public_emails(page, leads: list[dict], keyword: str = "", limit: int = 25) -> int:
    """Fill lead assets using the customer-development priority order."""
    found = 0
    checked = 0
    for lead in leads:
        _apply_customer_development_rules(lead)
        if checked >= limit:
            break
        profile_url = str(lead.get("profile_url") or "").strip()
        tags = lead.get("tags") or []
        metadata = lead.get("metadata") or {}
        has_core_assets = bool(metadata.get("website") or lead.get("email"))
        if "linkedin_text_result" in tags and not profile_url and not _clean_company_asset_name(metadata.get("company_name") or lead.get("username") or ""):
            continue
        if has_core_assets and metadata.get("linkedin_url") and lead.get("email"):
            continue
        checked += 1
        email = None
        before_email = bool(lead.get("email"))
        company_url = metadata.get("website") or (profile_url if _is_email_lookup_candidate(profile_url) else None)
        if not company_url and profile_url:
            profile_metadata = await _extract_assets_from_social_profile(page, lead)
            if profile_metadata:
                if profile_metadata.get("email") and not lead.get("email"):
                    lead["email"] = profile_metadata["email"]
                _merge_metadata(lead, {key: value for key, value in profile_metadata.items() if key != "email"})
                company_url = (lead.get("metadata") or {}).get("website")
        if not company_url:
            company_url = await _discover_company_site_from_search(page, lead, keyword)
        if company_url:
            _merge_metadata(lead, _extract_asset_metadata("", company_url, ""))
            _merge_metadata(lead, await _extract_company_assets_from_public_page(page, company_url))
            if not lead.get("email"):
                email = await _extract_email_from_public_page(page, company_url)
        if not lead.get("email") and not email:
            email = await _discover_email_from_search(page, lead, keyword)
        if email:
            lead["email"] = email
            tags = [tag for tag in (lead.get("tags") or []) if tag]
            if "email_found" not in tags:
                tags.append("email_found")
            lead["tags"] = tags
        metadata = lead.get("metadata") or {}
        if not metadata.get("linkedin_url"):
            linkedin_url = await _discover_linkedin_asset_from_search(page, lead, keyword)
            if linkedin_url:
                _merge_metadata(lead, {"linkedin_url": linkedin_url})
        if not (lead.get("metadata") or {}).get("country"):
            country = _infer_country((lead.get("metadata") or {}).get("website") or profile_url, " ".join(tags))
            if country:
                _merge_metadata(lead, {"country": country})
        _apply_customer_development_rules(lead)
        metadata = lead.get("metadata") or {}
        has_outreach_assets = bool(metadata.get("website") and lead.get("email"))
        metadata["enrichment_status"] = "outreach_ready" if has_outreach_assets else "missing_public_contact"
        if not has_outreach_assets:
            metadata["enrichment_note"] = "No public business email was found; verify the company website before outreach."
        lead["metadata"] = metadata
        if lead.get("email") and not before_email:
            found += 1
    return found


@router.post("/enrich-assets")
async def enrich_lead_assets(request: AssetEnrichmentRequest, current_user=Depends(get_current_user)):
    """Apply the foreign-trade customer-development rules to existing leads."""
    from db import get_db_pool as _get_pool

    requested_platform = str(request.platform or "all").lower()
    platform_filter = None
    if requested_platform in {"x", "twitter"}:
        platform_filter = ["x", "twitter"]
    elif requested_platform and requested_platform != "all":
        platform_filter = [requested_platform]

    pool_db = await _get_pool()
    async with pool_db.acquire() as conn:
        if request.lead_ids:
            rows = await conn.fetch(
                f"""SELECT id, platform, username, profile_url, email, followers, tags, status, metadata, quality_score, user_id, created_at
                   FROM leads
                   WHERE user_id = $1 AND id = ANY($2::int[])
                   ORDER BY created_at DESC
                   LIMIT $3""",
                current_user.id,
                request.lead_ids,
                request.limit,
            )
        else:
            platform_sql = "AND platform = ANY($3::text[])" if platform_filter else ""
            rows = await conn.fetch(
                f"""SELECT id, platform, username, profile_url, email, followers, tags, status, metadata, quality_score, user_id, created_at
                   FROM leads
                   WHERE user_id = $1
                   {platform_sql}
                   ORDER BY created_at DESC
                   LIMIT $2""",
                current_user.id,
                request.limit,
                *( [platform_filter] if platform_filter else [] ),
            )
    leads: list[dict[str, Any]] = []
    for row in rows:
        lead = dict(row)
        metadata = lead.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        lead["metadata"] = metadata
        lead["email"] = sanitize_lead_email(lead.get("email"))
        lead["tags"] = list(lead.get("tags") or [])
        leads.append(lead)
    if not leads:
        raise HTTPException(status_code=404, detail="No owned leads found")

    pool = get_browser_pool()
    if not pool._started:
        await pool.start()

    configured_user_data_dir = os.getenv("CHROME_USER_DATA_DIR")
    if configured_user_data_dir and not os.path.isdir(configured_user_data_dir):
        configured_user_data_dir = None
    user_data_dir = configured_user_data_dir or _auto_detect_chrome_user_data_dir()
    cdp_url = os.getenv("CDP_URL")
    context_id = f"asset_enrich_{id(request)}"
    context_id, context, instance = await pool.acquire_context(
        context_id=context_id,
        user_data_dir=user_data_dir,
        cdp_url=cdp_url,
    )

    try:
        page = await context.new_page()
        try:
            from playwright_stealth import Stealth

            await Stealth().apply_stealth_async(page)
        except Exception:
            pass
        await page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        })
        counts_before = _asset_presence_counts(leads)
        emails_before = sum(1 for lead in leads if lead.get("email"))
        enriched_email_count = await _enrich_leads_with_public_emails(
            page,
            leads,
            keyword=request.keyword,
            limit=request.limit,
        )
        # Enrich only the selected leads. Keyword-wide discovery belongs to a
        # separate prospecting workflow and must not add unrelated companies here.
        company_asset_leads: list[dict[str, Any]] = []
        for lead in leads:
            metadata = lead.get("metadata") or {}
            metadata["last_enriched_at"] = datetime.utcnow().isoformat()
            lead["metadata"] = metadata
        counts_after = _asset_presence_counts(leads)
        await page.close()
    finally:
        await pool.release_context(context_id, instance.instance_id)

    async with pool_db.acquire() as conn:
        for lead in leads:
            metadata = lead.get("metadata") or {}
            await conn.execute(
                """UPDATE leads
                   SET email = COALESCE($3, email),
                       tags = $4,
                       metadata = COALESCE(metadata, '{}'::jsonb) || $5::jsonb,
                       quality_score = $6
                   WHERE id = $1 AND user_id = $2""",
                lead["id"],
                current_user.id,
                sanitize_lead_email(lead.get("email")),
                lead.get("tags") or [],
                json.dumps(metadata, ensure_ascii=False, default=str),
                int(metadata.get("quality_score") or 0),
            )
    if company_asset_leads:
        from db import save_leads

        await save_leads(company_asset_leads, current_user.id)

    emails_after = sum(1 for lead in leads if lead.get("email"))
    company_counts = _asset_presence_counts(company_asset_leads)
    return {
        "status": "success",
        "rules_version": _customer_development_rules().get("version", "fallback"),
        "enriched": len(leads),
        "created_assets": len(company_asset_leads),
        "emails_enriched": enriched_email_count,
        "emails_found": max(0, emails_after - emails_before),
        "fields_found": counts_after,
        "fields_added": {
            field: max(0, counts_after.get(field, 0) - counts_before.get(field, 0))
            for field in counts_after
        },
        "created_fields_found": company_counts,
        "debug": _asset_debug_summary(leads, request.keyword),
        "data": leads,
        "created_data": company_asset_leads,
    }


@router.post("/test-scraper")
async def test_scraper(request: ScrapeRequest, current_user=Depends(get_current_user)):
    """
    Trigger LeadAgent for real scraping using the persistent browser pool.
    Supports multiple platforms: x, twitter, linkedin, instagram, shopify
    This endpoint uses the browser pool instead of starting/closing browser per request.
    """
    try:
        import sys
        # Windows 事件循环修复
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        # 获取浏览器池
        pool = get_browser_pool()

        # 确保池已启动
        if not pool._started:
            await pool.start()

        # 解析代理配置
        proxy_url = os.getenv("SCRAPER_PROXY")
        proxy_config = None
        if proxy_url:
            proxy_config = {"host": proxy_url}

        # 读取 Chrome 用户数据目录（用于保持登录态）。配置路径不存在时自动回退检测，
        # 避免机器用户名变化导致 LinkedIn 登录态不可用。
        configured_user_data_dir = os.getenv("CHROME_USER_DATA_DIR")
        if configured_user_data_dir and not os.path.isdir(configured_user_data_dir):
            print(f"[API] CHROME_USER_DATA_DIR does not exist: {configured_user_data_dir}; auto-detecting")
            configured_user_data_dir = None
        user_data_dir = configured_user_data_dir or _auto_detect_chrome_user_data_dir()

        # 读取 CDP URL（优先使用，保持登录态更稳定）
        cdp_url = os.getenv("CDP_URL")

        # 从池中获取 context
        context_id = f"scrape_{request.platform}_{id(request)}"
        context_id, context, instance = await pool.acquire_context(
            context_id=context_id,
            proxy=proxy_config,
            user_data_dir=user_data_dir,
            cdp_url=cdp_url
        )

        try:
            # 使用 Playwright Stealth 避免被检测
            from playwright_stealth import Stealth

            page = await context.new_page()
            stealth = Stealth()

            # 应用 stealth 配置，模拟真实浏览器
            await stealth.apply_stealth_async(page)

            # 设置更真实的浏览器属性
            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            })

            leads = []
            platform = request.platform.lower()
            scrape_source = platform
            print(f"[API] Starting scrape: platform={platform}, keyword={request.keyword}")

            # 根据平台选择爬取函数
            if platform in ["twitter", "x"]:
                leads = await _scrape_twitter(page, request.keyword)
            elif platform == "linkedin":
                leads = await _scrape_linkedin(page, request.keyword)
            elif platform == "instagram":
                leads = await _scrape_instagram(page, request.keyword)
            elif platform == "shopify":
                leads = await _scrape_shopify(page, request.keyword, request.store_domain)
            elif platform == "google":
                leads = await _scrape_google(page, request.keyword)
            elif platform == "directory":
                leads = await _scrape_public_directory(page, request.keyword)
            elif platform == "tiktok":
                leads = await _scrape_tiktok(page, request.keyword)
            elif platform == "facebook":
                leads = await _scrape_facebook(page, request.keyword)
            elif platform == "duckduckgo":
                leads = await _scrape_duckduckgo(page, request.keyword)
            else:
                # 未知平台，返回 mock
                pass
            direct_result_count = len(leads)
            direct_page_url = page.url

            # 平台直连爬取失败时，仅回退到该平台的公开索引。不要用其它平台
            # 的结果冒充当前平台线索，否则会污染线索质量和后续资产补全范围。
            if not leads and platform not in ["google", "directory", "duckduckgo"]:
                print(f"[API] {platform} returned 0 leads, searching public {platform} profile index")
                scrape_source = f"{platform}+public_search"
                leads = await _scrape_platform_search_fallback(page, request.keyword, platform)


            # 应用扩展参数过滤
            if request.geography != "all":
                leads = [l for l in leads if _match_geography(l, request.geography)]
            if request.follower_range != "all":
                leads = [l for l in leads if _match_follower_range(l, request.follower_range)]
            if request.content_type != "all":
                leads = [l for l in leads if _match_content_type(l, request.content_type)]
            if request.max_results > 0 and len(leads) > request.max_results:
                leads = leads[:request.max_results]
            scraped_social_count = len(leads)
            emails_before_enrichment = sum(1 for lead in leads if lead.get("email"))
            company_asset_leads: list[dict[str, Any]] = []
            # Keep social profiles even when public website/email fields are empty.
            # Deep company discovery runs only from /enrich-assets on user request.
            dropped_empty_social = 0
            enriched_email_count = 0
            emails_found = sum(1 for lead in leads if lead.get("email"))
            if enriched_email_count:
                print(f"[API] Email enrichment: found {enriched_email_count} additional emails")
            for lead in leads:
                _apply_customer_development_rules(lead)

            await page.close()

            # 保存真实数据到数据库（跳过空结果，不写入伪造数据）
            if leads:
                from db import save_leads
                await save_leads(leads, current_user.id)

            diagnostics = {
                "direct_result_count": direct_result_count,
                "returned_result_count": len(leads),
            }
            if not leads:
                if "login" in direct_page_url.lower() or "checkpoint" in direct_page_url.lower():
                    diagnostics["reason"] = "login_required"
                elif direct_result_count:
                    diagnostics["reason"] = "filtered_by_targeting"
                else:
                    diagnostics["reason"] = "no_matching_profiles"

            return {
                "status": "success",
                "leads_found": len(leads),
                "emails_found": emails_found,
                "emails_enriched": max(0, emails_found - emails_before_enrichment),
                "company_assets_found": len(company_asset_leads),
                "asset_fields_found": _asset_presence_counts(company_asset_leads),
                "scraped_social_found": scraped_social_count,
                "empty_social_dropped": dropped_empty_social,
                "source": scrape_source,
                "context_id": context_id,
                "instance_id": instance.instance_id,
                "diagnostics": diagnostics,
                "data": leads
            }

        finally:
            # 释放 context（不关闭，保持连接复用）
            await pool.release_context(context_id, instance.instance_id)

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"[API] Scraping failed: {error_details}")

        # 写入错误日志
        import logging
        _logger = logging.getLogger(__name__)
        _logger.error(f"Scraping Error:\n{error_details}")

        return {"status": "error", "message": f"Scraping workflow failed: {repr(e)}"}


# 需要 datetime


# ========================
# SerpAPI 搜索端点 (合规的搜索结果)
# ========================

class SerpSearchRequest(BaseModel):
    keyword: str = "fitness equipment"
    engine: str = "google"  # google, bing, yahoo, yandex, baidu, youtube, amazon, etc.
    num_results: int = 10


@router.post("/serp-search")
async def serpapi_search(request: SerpSearchRequest, current_user=Depends(get_current_user)):
    """
    使用 SerpAPI 进行合规的搜索引擎结果爬取

    支持的引擎:
    - google: Google 搜索结果
    - bing: Bing 搜索结果
    - yahoo: Yahoo 搜索结果
    - yandex: Yandex 搜索结果
    - baidu: 百度搜索结果
    - youtube: YouTube 视频搜索
    - amazon: Amazon 产品搜索
    - ebay: eBay 产品搜索

    申请 SerpAPI Key: https://serpapi.com
    """
    serpapi_key = os.getenv("SERPAPI_KEY")

    if not serpapi_key:
        return {
            "status": "error",
            "message": "SerpAPI key not configured. Set SERPAPI_KEY in .env file. Get your key at https://serpapi.com"
        }

    try:
        from serpapi import GoogleSearch, BingSearch, EbaySearch, AmazonSearch, YoutubeSearch

        params = {
            "q": request.keyword,
            "num": request.num_results,
            "api_key": serpapi_key
        }

        leads = []
        search_results = None

        if request.engine == "google":
            search_results = GoogleSearch(params)
        elif request.engine == "bing":
            search_results = BingSearch(params)
        elif request.engine == "amazon":
            search_results = AmazonSearch(params)
        elif request.engine == "youtube":
            search_results = YoutubeSearch(params)
            params["search_query"] = params.pop("q")
        else:
            # Default to Google
            search_results = GoogleSearch(params)

        data = search_results.get_dict()

        # Parse results based on engine
        if request.engine == "google":
            if "organic_results" in data:
                for result in data["organic_results"][:request.num_results]:
                    leads.append({
                        "platform": "google",
                        "username": result.get("title", ""),
                        "profile_url": result.get("link", ""),
                        "email": None,
                        "followers": 0,
                        "tags": [request.keyword, result.get("displayed_link", "")],
                        "snippet": result.get("snippet", "")
                    })
        elif request.engine == "bing":
            if "organic_results" in data:
                for result in data["organic_results"][:request.num_results]:
                    leads.append({
                        "platform": "bing",
                        "username": result.get("title", ""),
                        "profile_url": result.get("link", ""),
                        "email": None,
                        "followers": 0,
                        "tags": [request.keyword],
                        "snippet": result.get("snippet", "")
                    })
        elif request.engine == "youtube":
            if "video_results" in data:
                for result in data["video_results"][:request.num_results]:
                    leads.append({
                        "platform": "youtube",
                        "username": result.get("title", ""),
                        "profile_url": result.get("link", ""),
                        "email": None,
                        "followers": int(result.get("views", "0").replace(",", "")) if result.get("views") else 0,
                        "tags": [request.keyword, result.get("channel", "")],
                        "duration": result.get("duration", "")
                    })
        elif request.engine == "amazon":
            if "organic_results" in data:
                for result in data["organic_results"][:request.num_results]:
                    leads.append({
                        "platform": "amazon",
                        "username": result.get("title", ""),
                        "profile_url": result.get("link", ""),
                        "email": None,
                        "followers": 0,
                        "tags": [request.keyword, result.get("price", ""), result.get("rating", "")],
                        "snippet": result.get("snippet", "")
                    })

        # Save to database
        if leads:
            from db import save_leads
            await save_leads(leads, current_user.id)

        return {
            "status": "success",
            "leads_found": len(leads),
            "engine": request.engine,
            "keyword": request.keyword,
            "data": leads
        }

    except ImportError:
        return {
            "status": "error",
            "message": "SerpAPI library not installed. Run: pip install google-search-results"
        }
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"[API] SerpAPI search failed: {error_details}")
        return {
            "status": "error",
            "message": f"SerpAPI search failed: {str(e)}"
        }


# ========================
# Browser Harness Endpoints
# ========================

class HarnessScrapeRequest(BaseModel):
    keyword: str = "fitness equipment"
    platform: str = "x"
    action: str = "scrape"  # scrape | follow | message | connect | profile
    username: Optional[str] = None
    message: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)
    dry_run: bool = False


@router.post("/harness-scrape")
async def harness_scrape(
    request: HarnessScrapeRequest,
    current_user=Depends(get_current_user)
):
    """
    Execute a browser-harness based task.
    Connects to the user's real Chrome browser for authenticated scraping and interaction.
    """
    from browser_cluster.manager.browser_harness_manager import get_harness_manager

    harness_mgr = await get_harness_manager()
    if not harness_mgr.is_connected:
        await harness_mgr.start()
    if not harness_mgr.is_connected:
        return {
            "status": "error",
            "message": (
                "Browser harness not connected. Verify browser-harness 0.1.3+ is installed, "
                "Chrome is running with --remote-debugging-port=9222, and remote debugging is allowed in Chrome."
            ),
        }

    try:
        from agents.harness_agent.harness_agent import HarnessAgent
        agent = HarnessAgent(
            harness_manager=harness_mgr,
            db=None,
            dry_run=request.dry_run,
        )

        task = {
            "action": request.action,
            "platform": request.platform,
            "keyword": request.keyword,
            "username": request.username or "",
            "message": request.message or "",
            "limit": request.limit,
            "user_id": current_user.id,
        }

        result = await agent.run(task)

        # Save leads to database if scraping
        if result.get("status") == "success" and result.get("data"):
            try:
                from db import save_leads
                await save_leads(result["data"], current_user.id)
            except Exception as e:
                print(f"[API] Failed to save harness leads: {e}")

        return result

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"[API] Harness scrape failed: {error_details}")
        return {"status": "error", "message": str(e)}


@router.get("/harness-status")
async def harness_status(current_user=Depends(get_current_user)):
    """Get browser-harness connection status."""
    from browser_cluster.manager.browser_harness_manager import get_harness_manager
    from browser_cluster.harness_launcher import is_debug_port_open, get_ws_debug_url

    harness_mgr = await get_harness_manager()
    chrome_running = is_debug_port_open()

    return {
        "harness_connected": harness_mgr.is_connected,
        "chrome_debug_port": chrome_running,
        "ws_debug_url": get_ws_debug_url() if chrome_running else None,
    }


# ========================
# Marketing Pipeline (Research + Chat Agents)
# ========================

import json
import re as _re

_pipeline_semaphore = asyncio.Semaphore(3)

RESEARCH_SYSTEM_PROMPT = """You are a B2B lead research analyst for cross-border e-commerce. Use only these five files as the business standard:
- product_brief.md: main product is "用户填写"; core advantage is "用户填写".
- target_market.md: target Europe and North America; prioritize engineering distributors, lighting contractors, renovation companies; do not develop retailers, trading middlemen, or price-only contacts.
- scoring_rules.md: S=8-10, A=5-7, B=3-4, C=<3 abandon. Score = industry fit 3 + annual purchase volume 2 + existing supplier pain 2 + decision-maker accessibility 2 + project urgency 1.
- email_style.md: direct professional tone; first sentence must mention the customer's specific project or product; do not quote price upfront; end by guiding the customer to ask about lead time or available stock; never use "hope this email finds you well".
- follow_up_sop.md: day 3 follow-up, day 7 case, day 14 project progress; after 30 days without reply downgrade to C.

Analyze the given lead profile and return a JSON object with these fields:
- "industry": the lead's likely business type or industry (1-5 words, in English)
- "interests": array of 2-4 potential business interests or needs (in English)
- "best_channel": either "email" or "social_dm" based on which outreach method would be most effective
- "talking_points": array of 2-3 personalized conversation starters based on their profile (in English)
- "quality_score": integer 0-10 based only on scoring_rules.md
- "tier": "S" for 8-10, "A" for 5-7, "B" for 3-4, "C" for <3
- "score_breakdown": object with industry_fit, annual_purchase, supplier_pain, decision_access, urgency
- "disqualified": true only for retailers, trading middlemen, or price-only contacts

The marketing pipeline always creates customer-facing outreach in English, even if the app UI is Chinese.
Write every descriptive field in natural business English. Do not use Chinese or any other non-English language.
Respond with ONLY valid JSON, no markdown, no explanation."""

CHAT_SYSTEM_PROMPT = """You are a B2B marketing copywriter for cross-border e-commerce. Given a lead's research profile, generate personalized outreach messages for 3 channels. Return a JSON object with a "messages" array containing exactly 3 objects, each with:
- "channel": "email", "linkedin_dm", or "twitter_dm"
- "subject": email subject line (empty string for non-email channels)
- "body": the message body (twitter_dm must be under 280 characters)
- "cta": call to action text

Guidelines:
- Reference specific project or product details from the lead's profile and interests in the first sentence.
- Do not generate outreach for C-tier or disqualified leads.
- Use a direct professional tone; no generic pleasantries.
- Do not quote price upfront.
- Do not invent products beyond product_context, prices, discounts, customer names, case studies, guarantees, or capabilities.
- End each message by guiding the customer to ask about lead time or available stock.
- Never use "hope this email finds you well".
- The marketing pipeline always creates customer-facing outreach in English, even if the app UI is Chinese.
- Write subject, body, and cta in natural business English only. Do not use Chinese or any other non-English language.

Respond with ONLY valid JSON, no markdown."""


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences from LLM response."""
    text = text.strip()
    text = _re.sub(r'^```(?:json)?\s*', '', text)
    text = _re.sub(r'\s*```$', '', text)
    return text.strip()


def _lead_fallback_research(lead: dict) -> dict:
    """Fallback research when LLM fails."""
    tag_values = [str(tag).strip() for tag in lead.get("tags", []) if str(tag).strip()]
    english_tags = [tag for tag in tag_values if not _contains_non_english_script(tag)]
    industry = english_tags[0] if english_tags else "Unknown"
    scoring = score_lead(lead, {"industry": industry, "interests": english_tags})
    return {
        "industry": industry,
        "interests": english_tags[:3] or ["project procurement"],
        "best_channel": "email" if lead.get("email") else "social_dm",
        "talking_points": [first_specific_signal(lead, {"industry": industry, "interests": english_tags})],
        "quality_score": scoring["score"],
        "tier": scoring["tier"],
        "score_breakdown": scoring["breakdown"],
        "disqualified": is_disqualified_lead(lead, {"industry": industry, "interests": english_tags}),
    }


def _clean_research_result(result: dict, lead: dict) -> dict:
    """Normalize LLM research fields before they reach message generation or storage."""
    fallback = _lead_fallback_research(lead)
    if not isinstance(result, dict):
        return fallback
    try:
        raw_score = int(result.get("quality_score", fallback["quality_score"]))
        score = min(10, max(0, raw_score if raw_score <= 10 else round(raw_score / 10)))
    except (TypeError, ValueError):
        score = fallback["quality_score"]

    def clean_list(key: str, maximum: int) -> list[str]:
        values = result.get(key)
        if not isinstance(values, list):
            return fallback[key]
        cleaned = [str(value).strip() for value in values if str(value).strip()][:maximum]
        if any(_contains_non_english_script(value) for value in cleaned):
            return fallback[key]
        return cleaned or fallback[key]

    industry = str(result.get("industry") or fallback["industry"]).strip()[:80]
    if not industry or any(marker in industry for marker in ("\ufffd", "锛", "銆", "鈥")) or _contains_non_english_script(industry):
        industry = fallback["industry"]
    cleaned = {
        "industry": industry,
        "interests": clean_list("interests", 4),
        "best_channel": result.get("best_channel") if result.get("best_channel") in {"email", "social_dm"} else fallback["best_channel"],
        "talking_points": clean_list("talking_points", 3),
        "quality_score": score,
        "tier": "S" if score >= 8 else ("A" if score >= 5 else ("B" if score >= 3 else "C")),
        "score_breakdown": result.get("score_breakdown") if isinstance(result.get("score_breakdown"), dict) else fallback["score_breakdown"],
        "disqualified": bool(result.get("disqualified")) or is_disqualified_lead(lead, result),
    }
    if cleaned["disqualified"]:
        cleaned["quality_score"] = 0
        cleaned["tier"] = "C"
    return cleaned


async def _research_lead(client, lead: dict, product_context: str, language: str) -> dict:
    """Research Agent: analyze a single lead via LLM."""
    if client is None:
        return _lead_fallback_research(lead)
    async with _pipeline_semaphore:
        try:
            user_prompt = f"""Lead profile:
- Platform: {lead.get('platform', 'unknown')}
- Username: {lead.get('username', 'unknown')}
- Profile URL: {lead.get('profile_url', 'none')}
- Email: {lead.get('email') or 'none'}
- Followers: {lead.get('followers', 0)}
- Tags: {lead.get('tags', [])}"""

            if product_context:
                user_prompt += f"\n\nProduct context: {product_context}"
            user_prompt += "\n\nIMPORTANT: Write ALL fields (industry, interests, talking_points) in English only. Do not use Chinese or any other non-English language."

            response, _ = await _create_marketing_completion(
                client,
                messages=[
                    {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.25,
                max_tokens=500
            )
            raw = response.choices[0].message.content
            result = json.loads(_strip_json_fences(raw))
            return _clean_research_result(result, lead)
        except Exception as e:
            print(f"[ResearchAgent] Failed for {lead.get('username')}: {e}")
            return _lead_fallback_research(lead)


async def _generate_messages(client, lead: dict, research: dict, product_context: str, language: str) -> list:
    """Chat Agent: generate personalized outreach messages."""
    if research.get("tier") == "C" or research.get("disqualified") or is_disqualified_lead(lead, research):
        return []
    if client is None:
        return _fallback_messages(lead, research, language)
    async with _pipeline_semaphore:
        try:
            user_prompt = f"""Lead research:
- Username: {lead.get('username', 'unknown')}
- Platform: {lead.get('platform', 'unknown')}
- Industry: {research.get('industry', 'Unknown')}
- Interests: {research.get('interests', [])}
- Best channel: {research.get('best_channel', 'email')}
- Talking points: {research.get('talking_points', [])}
- Quality tier: {research.get('tier', 'C')}
- Score breakdown: {research.get('score_breakdown', {})}
- Followers: {lead.get('followers', 0)}
- Email: {lead.get('email') or 'none'}"""

            if product_context:
                user_prompt += f"\n\nProduct context: {product_context}"
            user_prompt += f"""\n
Target markets: {", ".join(TARGET_MARKETS)}
Priority customer types: {", ".join(PRIORITY_CUSTOMERS)}

IMPORTANT: Write ALL messages (subject, body, cta) in English only. Do not use Chinese or any other non-English language."""

            response, _ = await _create_marketing_completion(
                client,
                messages=[
                    {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.35,
                max_tokens=1500
            )
            raw = response.choices[0].message.content
            result = json.loads(_strip_json_fences(raw))
            messages = result.get("messages", [])
            if not isinstance(messages, list) or {msg.get("channel") for msg in messages} != {"email", "linkedin_dm", "twitter_dm"}:
                return _fallback_messages(lead, research, language)
            for msg in messages:
                if not _is_usable_marketing_text(msg.get("body", ""), language):
                    return _fallback_messages(lead, research, language)
                if msg.get("channel") == "twitter_dm" and len(msg.get("body", "")) > 280:
                    msg["body"] = msg["body"][:277] + "..."
            return messages if messages else _fallback_messages(lead, research, language)
        except Exception as e:
            print(f"[ChatAgent] Failed for {lead.get('username')}: {e}")
            return _fallback_messages(lead, research, language)


def _fallback_messages(lead: dict, research: dict, language: str) -> list:
    """Fallback messages when LLM fails."""
    if research.get("tier") == "C" or research.get("disqualified") or is_disqualified_lead(lead, research):
        return []
    username = lead.get("username", "")
    industry = research.get("industry", "your project")
    if language == "en" and _contains_non_english_script(str(industry)):
        industry = "your project"
    if language == "zh":
        return [
            {"channel": "email", "subject": f"关于 {industry} 的合作机会", "body": f"您好，{username}：\n\n关注到您在 {industry} 领域的持续投入。我们正在帮助相关团队提升获客与转化效率，希望了解您当前最关注的增长方向。\n\n如果您方便，是否可以安排一次 15 分钟沟通？", "cta": "预约 15 分钟交流"},
            {"channel": "linkedin_dm", "subject": "", "body": f"您好，{username}。关注到您在 {industry} 领域的内容，很有启发。我们正在帮助相关团队提升获客效率，方便交流一下您当前的增长重点吗？", "cta": "交流增长重点"},
            {"channel": "twitter_dm", "subject": "", "body": f"您好，{username}。看到您分享的 {industry} 内容，很有启发。我们在帮助相关团队优化获客与转化，方便简单交流一下吗？", "cta": "简单交流"}
        ]
    else:
        signal = first_specific_signal(lead, research)
        return [
            {"channel": "email", "subject": subject_for_signal(signal), "body": initial_email_body(lead, research, ""), "cta": "Check lead time or stock"},
            {"channel": "linkedin_dm", "subject": "", "body": f"Hi {username}, I saw your work on {signal}. Before discussing price, should I check lead time or available stock for your current project?", "cta": "Check lead time or stock"},
            {"channel": "twitter_dm", "subject": "", "body": f"Hi {username}, I saw your work on {signal}. Should I check lead time or available stock for your current project?", "cta": "Check lead time or stock"}
        ]


@router.post("/marketing-pipeline")
async def marketing_pipeline(
    request: MarketingPipelineRequest,
    current_user=Depends(get_current_user)
):
    """
    Full marketing pipeline: Research Agent + Chat Agent.
    Analyzes each lead and generates personalized multi-channel messages.
    """
    try:
        client = _get_llm_client()
        generation_mode = "openrouter"
    except RuntimeError:
        client = None
        generation_mode = "local_fallback"

    from db import get_db_pool as _get_pool
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, platform, username, profile_url, email, followers, tags
               FROM leads
               WHERE user_id = $1 AND id = ANY($2::int[])
               ORDER BY created_at DESC""",
            current_user.id, request.lead_ids,
        )
    leads = [dict(row) for row in rows]
    if not leads:
        raise HTTPException(status_code=404, detail="No owned leads found")

    product_context = request.product_context
    # UI language should not control outbound copy language. This pipeline targets
    # cross-border prospects, so generated outreach must remain English.
    language = "en"
    user_id = current_user.id

    # Stage 1: Research Agent — analyze all leads concurrently
    research_tasks = [_research_lead(client, lead, product_context, language) for lead in leads]
    research_results = await asyncio.gather(*research_tasks)

    # Stage 2: Chat Agent — generate messages for each lead
    message_tasks = [
        _generate_messages(client, leads[i], research_results[i], product_context, language)
        for i in range(len(leads))
    ]
    all_messages = await asyncio.gather(*message_tasks)

    # Stage 3: Save to database and build response
    tier_distribution = {"S": 0, "A": 0, "B": 0, "C": 0}
    results = []
    db_messages = []
    from db import create_marketing_campaign
    campaign_name = f"{product_context.strip()} Outreach" if product_context.strip() else f"Pipeline Outreach - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    campaign_id = await create_marketing_campaign(
        user_id=user_id,
        name=campaign_name[:255],
        product_context=product_context,
        lead_count=len(leads),
        generation_mode=generation_mode,
    )

    for i, lead in enumerate(leads):
        research = research_results[i]
        messages = all_messages[i]

        tier = research.get("tier", "C")
        tier_distribution[tier if tier in tier_distribution else "C"] += 1

        # Save research to leads table
        lead_id = lead.get("id")
        if lead_id:
            from db import save_lead_research, save_marketing_messages
            await save_lead_research(lead_id, user_id, research, research.get("quality_score", 0))

        # Prepare messages for DB
        for msg in messages:
            db_messages.append({
                "lead_id": lead_id,
                "user_id": user_id,
                "campaign_id": campaign_id,
                "channel": msg.get("channel", ""),
                "subject": msg.get("subject", ""),
                "body": msg.get("body", ""),
                "cta": msg.get("cta", ""),
                "sequence_step": 1,
                "status": "draft"
            })

        results.append({
            "lead": {
                "id": lead_id,
                "username": lead.get("username", ""),
                "platform": lead.get("platform", ""),
                "profile_url": lead.get("profile_url", ""),
                "followers": lead.get("followers", 0)
            },
            "research": research,
            "messages": messages
        })

    # Batch save messages
    if db_messages:
        from db import save_marketing_messages
        await save_marketing_messages(db_messages)

    return {
        "status": "success",
        "summary": {
            "campaign_id": campaign_id,
            "total_leads": len(leads),
            "researched": len(research_results),
            "messages_generated": sum(len(m) for m in all_messages),
            "tier_distribution": tier_distribution,
            "generation_mode": generation_mode,
        },
        "results": results
    }


@router.post("/acquisition-pipeline")
async def acquisition_pipeline(
    request: AcquisitionPipelineRequest,
    current_user=Depends(get_current_user),
):
    """Search prioritized platforms, persist assets, then draft email outreach.

    The existing scraper owns enrichment and idempotent lead persistence. This
    orchestration intentionally stops at draft creation; approval and delivery
    continue through the guarded Chat Agent endpoints.
    """
    keyword = request.keyword.strip()
    platform_runs = []
    successful_platforms: list[str] = []
    seen_platforms: set[str] = set()

    for target in _ordered_acquisition_platforms(request.platforms):
        platform = "x" if target.platform == "twitter" else target.platform
        if platform in seen_platforms:
            continue
        seen_platforms.add(platform)
        result = await test_scraper(
            ScrapeRequest(
                keyword=keyword,
                platform=platform,
                max_results=request.max_results_per_platform,
            ),
            current_user=current_user,
        )
        run = {
            "platform": platform,
            "priority": target.priority,
            "status": result.get("status", "error"),
            "leads_found": int(result.get("leads_found") or 0),
            "emails_found": int(result.get("emails_found") or 0),
            "source": result.get("source", platform),
        }
        if run["status"] != "success":
            run["error"] = result.get("message", "Platform search failed")
        else:
            successful_platforms.append(platform)
        platform_runs.append(run)

    lead_ids: list[int] = []
    if successful_platforms:
        from db import get_db_pool as _get_pool

        pool = await _get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id
                   FROM leads
                   WHERE user_id = $1
                     AND platform = ANY($2::text[])
                     AND email IS NOT NULL AND BTRIM(email) <> ''
                     AND $3 = ANY(COALESCE(tags, '{}'::text[]))
                   ORDER BY quality_score DESC, created_at DESC, id DESC
                   LIMIT $4""",
                current_user.id,
                successful_platforms,
                keyword,
                request.max_outreach_leads,
            )
        lead_ids = [row["id"] for row in rows]

    outreach = None
    if lead_ids:
        outreach = await marketing_pipeline(
            MarketingPipelineRequest(
                lead_ids=lead_ids,
                product_context=request.product_context or keyword,
                language="en",
            ),
            current_user=current_user,
        )

    failed = sum(run["status"] != "success" for run in platform_runs)
    return {
        "status": "success" if failed == 0 else "partial_success",
        "keyword": keyword,
        "platform_runs": platform_runs,
        "assets_persisted": sum(run["leads_found"] for run in platform_runs),
        "email_ready_lead_ids": lead_ids,
        "outreach": outreach,
        "next_action": "review_drafts" if outreach else "refine_search_for_public_emails",
    }


# ─── Skill Execution ──────────────────────────────────────────────

class SkillExecuteRequest(BaseModel):
    skill_id: str
    input_text: str = ""
    language: str = "en"


_SKILL_PROMPTS = {
    "s1": {
        "system": "You are a professional multilingual translator. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Translate the following text into English, Chinese, Spanish, French, and German.\n\nText:\n{input}\n\nReturn JSON:\n{{\"translations\": [{{\"lang\": \"en\", \"text\": \"...\"}}, {{\"lang\": \"zh\", \"text\": \"...\"}}, {{\"lang\": \"es\", \"text\": \"...\"}}, {{\"lang\": \"fr\", \"text\": \"...\"}}, {{\"lang\": \"de\", \"text\": \"...\"}}]}}"
    },
    "s2": {
        "system": "You are a market research analyst. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Analyze the top competitors for the following product/niche/leads data. Identify strengths, weaknesses, and market opportunities.\n\nContext:\n{input}\n\nReturn JSON:\n{{\"competitors\": [{{\"name\": \"...\", \"strengths\": [\"...\"], \"weaknesses\": [\"...\"], \"opportunities\": [\"...\"]}}], \"market_trends\": [\"...\"], \"recommendation\": \"...\"}}"
    },
    "s3": {
        "system": "You are an email marketing expert specializing in high-open-rate subject lines. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Generate 10 high-open-rate email subject lines for the following product/niche/campaign.\n\nContext:\n{input}\n\nReturn JSON:\n{{\"subjects\": [{{\"text\": \"...\", \"predicted_open_rate\": \"35%\", \"rationale\": \"...\"}}]}}"
    },
    "s4": {
        "system": "You are a LinkedIn outreach specialist. Write professional, personalized DMs. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Generate 3 LinkedIn outreach DM variants for the following lead/context. Each variant should have a different tone (professional, friendly, bold).\n\nContext:\n{input}\n\nReturn JSON:\n{{\"scripts\": [{{\"variant\": \"Professional\", \"opener\": \"...\", \"body\": \"...\", \"cta\": \"...\", \"tone\": \"professional\"}}, {{\"variant\": \"Friendly\", \"opener\": \"...\", \"body\": \"...\", \"cta\": \"...\", \"tone\": \"friendly\"}}, {{\"variant\": \"Bold\", \"opener\": \"...\", \"body\": \"...\", \"cta\": \"...\", \"tone\": \"bold\"}}]}}"
    },
    "s5": {
        "system": "You are a conversion rate optimization expert. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Given the following marketing copy, generate 3 A/B test variants. Each variant should change a different element (headline, CTA, tone).\n\nOriginal copy:\n{input}\n\nReturn JSON:\n{{\"variants\": [{{\"variant_id\": \"A\", \"text\": \"...\", \"change_description\": \"...\", \"hypothesis\": \"...\"}}, {{\"variant_id\": \"B\", \"text\": \"...\", \"change_description\": \"...\", \"hypothesis\": \"...\"}}, {{\"variant_id\": \"C\", \"text\": \"...\", \"change_description\": \"...\", \"hypothesis\": \"...\"}}]}}"
    },
    "s6": {
        "system": "You are a data quality analyst. Return valid JSON only, no markdown fences. Write ALL text content in {lang_name}.",
        "user_tpl": "Analyze the following leads data for quality issues. Flag duplicates, missing fields, invalid emails, suspicious entries, and low-quality records.\n\nLeads data:\n{input}\n\nReturn JSON:\n{{\"total\": 10, \"valid\": 8, \"issues_found\": 2, \"cleaned_leads\": [...], \"removed\": [...], \"issues\": [{{\"lead\": \"...\", \"reason\": \"...\"}}], \"summary\": \"...\"}}"
    },
}


@router.post("/execute-skill")
async def execute_skill(request: SkillExecuteRequest, current_user=Depends(get_current_user)):
    """Execute a skill module via LLM."""
    skill_id = request.skill_id
    if skill_id not in _SKILL_PROMPTS:
        raise HTTPException(status_code=400, detail=f"Unknown skill_id: {skill_id}")

    prompt_cfg = _SKILL_PROMPTS[skill_id]
    is_zh = request.language == "zh"
    lang_name = "Chinese" if is_zh else "English"
    system_prompt = prompt_cfg["system"].replace("{lang_name}", lang_name)
    user_content = prompt_cfg["user_tpl"].replace("{input}", request.input_text or ("(未提供输入)" if is_zh else "(no input provided)"))
    user_content += "\n\n" + ("请用中文回复所有文本内容。只返回纯JSON，不要用markdown代码块包裹。" if is_zh else "Write ALL text content in English. Return raw JSON only, do not wrap in markdown code blocks.")

    try:
        client = _get_llm_client()
        async with _pipeline_semaphore:
            response = await client.chat.completions.create(
                model="meta-llama/llama-3-8b-instruct",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                extra_headers={"HTTP-Referer": "http://localhost:8000", "X-Title": "OpenClaw AI Agent"},
                max_tokens=2000
            )
            raw = response.choices[0].message.content
            result = json.loads(_strip_json_fences(raw))
            return {"status": "success", "skill_id": skill_id, "result": result}
    except json.JSONDecodeError:
        # Try to fix common JSON issues from LLM output
        try:
            fixed = raw.strip()
            # Remove markdown code fences if present
            if fixed.startswith("```"):
                first_newline = fixed.index("\n")
                fixed = fixed[first_newline + 1:]
            if fixed.endswith("```"):
                fixed = fixed[:-3].rstrip()
            result = json.loads(fixed)
            return {"status": "success", "skill_id": skill_id, "result": result}
        except Exception:
            return {"status": "success", "skill_id": skill_id, "result": {"raw_output": raw}}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
