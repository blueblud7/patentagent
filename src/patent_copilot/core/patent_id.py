from __future__ import annotations

import re

KNOWN_COUNTRY_CODES = {
    "US",
    "EP",
    "WO",
    "KR",
    "JP",
    "CN",
    "DE",
    "FR",
    "GB",
}


def normalize_patent_id(value: str, *, default_country: str = "US") -> str:
    """Normalize common patent ID forms into a compact Google Patents-compatible ID."""

    cleaned = value.strip()
    cleaned = re.sub(r"https?://patents\.google\.com/patent/", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"/.*$", "", cleaned)
    cleaned = cleaned.upper()
    cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)
    if not cleaned:
        raise ValueError("Patent ID cannot be empty.")

    country = cleaned[:2]
    if country not in KNOWN_COUNTRY_CODES:
        cleaned = f"{default_country.upper()}{cleaned}"

    return cleaned


def google_patents_url(patent_id: str | None) -> str | None:
    if not patent_id:
        return None
    return f"https://patents.google.com/patent/{normalize_patent_id(patent_id)}/en"


def patentsview_numeric_id(patent_id: str) -> str:
    normalized = normalize_patent_id(patent_id, default_country="US")
    if not normalized.startswith("US"):
        return normalized
    numeric = re.sub(r"^US", "", normalized)
    return re.sub(r"[A-Z]\d?$", "", numeric)


def is_us_publication_id(patent_id: str) -> bool:
    numeric = patentsview_numeric_id(patent_id)
    return len(numeric) == 11 and numeric.startswith("20")
