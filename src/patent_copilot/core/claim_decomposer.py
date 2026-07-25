from __future__ import annotations

import re

from patent_copilot.core.schemas import ClaimElement
from patent_copilot.core.text import normalize_space


CONNECTOR_PATTERNS = [
    r"\band\b\s+(?=(?:a|an|the|said)\s+[a-zA-Z0-9-]+)",
    r";\s*(?:and\s+)?(?=(?:a|an|the|said|wherein)\s+)",
    r",\s*(?=wherein\b)",
]


def decompose_claim(claim_text: str) -> list[ClaimElement]:
    """Split one patent claim into reviewable elements.

    This is intentionally conservative. It favors fewer, legally meaningful chunks over
    atomizing every phrase, because a claim chart row should be useful to a practitioner.
    """

    cleaned = normalize_space(claim_text)
    cleaned = re.sub(r"^\s*\d+\.\s*", "", cleaned)
    cleaned = cleaned.replace(" comprising:", " comprising ")
    cleaned = cleaned.replace(" comprises:", " comprises ")

    preamble, body = _split_preamble(cleaned)
    chunks: list[str] = []
    if preamble:
        chunks.append(preamble)
    chunks.extend(_split_body(body))

    elements: list[ClaimElement] = []
    for idx, chunk in enumerate(chunks):
        text = normalize_space(chunk.strip(" ;,"))
        if not text:
            continue
        element_no = f"1{chr(ord('A') + len(elements))}"
        elements.append(ClaimElement(element_no=element_no, text=text))

    if not elements and cleaned:
        elements.append(ClaimElement(element_no="1A", text=cleaned))

    return elements


def _split_preamble(text: str) -> tuple[str | None, str]:
    match = re.search(r"\b(comprising|comprises|including|includes|having)\b", text, re.I)
    if not match:
        return None, text

    preamble = normalize_space(text[: match.end()])
    body = normalize_space(text[match.end() :])
    return preamble, body


def _split_body(body: str) -> list[str]:
    if not body:
        return []

    pattern = "|".join(f"(?:{part})" for part in CONNECTOR_PATTERNS)
    chunks = re.split(pattern, body, flags=re.I)

    merged: list[str] = []
    for chunk in chunks:
        chunk = normalize_space(chunk)
        if not chunk:
            continue
        if merged and _looks_like_modifier(chunk):
            merged[-1] = f"{merged[-1]}, {chunk}"
        else:
            merged.append(chunk)
    return merged


def _looks_like_modifier(text: str) -> bool:
    lowered = text.lower()
    return lowered.startswith(("to ", "for ", "based on ", "using ", "when "))

