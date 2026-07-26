from __future__ import annotations

from collections import Counter

from patent_copilot.core.schemas import ClaimElement, Evidence, PriorArtDocument
from patent_copilot.core.text import paragraph_locator, split_sentences, tokenize


def retrieve_evidence(
    element: ClaimElement,
    documents: list[PriorArtDocument],
    *,
    limit: int = 3,
) -> list[Evidence]:
    element_terms = Counter(tokenize(element.text))
    if not element_terms:
        return []

    candidates: list[Evidence] = []
    for document in documents:
        for section, section_text in document.searchable_sections():
            for passage in split_sentences(section_text):
                passage_terms = Counter(tokenize(passage))
                if not passage_terms:
                    continue
                score = _overlap_score(element_terms, passage_terms)
                if score <= 0:
                    continue
                matched_terms = _matched_terms(element_terms, passage_terms)
                missing_terms = _missing_terms(element_terms, passage_terms)
                candidates.append(
                    Evidence(
                        prior_art_id=document.id,
                        section=section,
                        locator=paragraph_locator(passage),
                        quote=passage,
                        score=round(score, 4),
                        why_relevant=_why_relevant(matched_terms, missing_terms),
                        matched_terms=matched_terms,
                        missing_terms=missing_terms,
                        term_coverage=round(len(matched_terms) / max(len(element_terms), 1), 4),
                    )
                )

    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:limit]


def _overlap_score(element_terms: Counter[str], passage_terms: Counter[str]) -> float:
    overlap = set(element_terms).intersection(passage_terms)
    if not overlap:
        return 0.0

    recall = len(overlap) / max(len(element_terms), 1)
    precision = len(overlap) / max(len(passage_terms), 1)
    phrase_bonus = 0.15 if len(overlap) >= 3 else 0.0
    return (0.7 * recall) + (0.3 * precision) + phrase_bonus


def _matched_terms(element_terms: Counter[str], passage_terms: Counter[str]) -> list[str]:
    return sorted(set(element_terms).intersection(passage_terms))


def _missing_terms(element_terms: Counter[str], passage_terms: Counter[str]) -> list[str]:
    return sorted(set(element_terms).difference(passage_terms))


def _why_relevant(matched_terms: list[str], missing_terms: list[str]) -> str:
    if not matched_terms:
        return "No material term overlap."
    terms = ", ".join(matched_terms[:8])
    message = f"Shares material terms with the claim element: {terms}."
    if missing_terms:
        missing = ", ".join(missing_terms[:8])
        message += f" Missing material terms: {missing}."
    return message
