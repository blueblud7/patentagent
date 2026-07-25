from __future__ import annotations

import re
import unicodedata


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "comprising",
    "configured",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "said",
    "the",
    "to",
    "wherein",
    "with",
}


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_token(token: str) -> str:
    token = unicodedata.normalize("NFKC", token).lower()
    token = re.sub(r"[^a-z0-9가-힣]+", "", token)
    if token.endswith("ing") and len(token) > 5:
        token = token[:-3]
    elif token.endswith("ed") and len(token) > 4:
        token = token[:-2]
    elif token.endswith("s") and len(token) > 4:
        token = token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    tokens = [normalize_token(token) for token in re.findall(r"[A-Za-z0-9가-힣]+", text)]
    return [token for token in tokens if token and token not in STOPWORDS and len(token) > 1]


def split_sentences(text: str) -> list[str]:
    text = normalize_space(text)
    if not text:
        return []

    paragraph_chunks = re.split(r"(?=\[\d{4}\])", text)
    sentences: list[str] = []
    for chunk in paragraph_chunks:
        chunk = normalize_space(chunk)
        if not chunk:
            continue
        parts = re.split(r"(?<=[.!?。])\s+(?=[A-Z0-9\[])|;\s+(?=[a-zA-Z0-9])", chunk)
        sentences.extend(normalize_space(part) for part in parts if normalize_space(part))
    return sentences


def paragraph_locator(text: str) -> str | None:
    match = re.search(r"\[(\d{4})\]", text)
    if match:
        return match.group(1)
    return None

