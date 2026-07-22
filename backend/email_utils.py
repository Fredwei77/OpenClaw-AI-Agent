from __future__ import annotations

BLOCKED_EMAIL_DOMAINS = {
    "duckduckgo.com",
    "google.com",
    "bing.com",
    "yahoo.com",
}

BLOCKED_EMAIL_ADDRESSES = {
    "error-lite@duckduckgo.com",
}


def sanitize_lead_email(email: str | None) -> str | None:
    """Return a usable public lead email, or None for search/system emails."""
    if not email:
        return None
    cleaned = str(email).strip().lower()
    if "@" not in cleaned:
        return None
    _, _, domain = cleaned.partition("@")
    if cleaned in BLOCKED_EMAIL_ADDRESSES:
        return None
    if domain in BLOCKED_EMAIL_DOMAINS:
        return None
    return cleaned
