from __future__ import annotations

from patent_copilot.adapters.base import PatentDataAdapter
from patent_copilot.core.schemas import PriorArtDocument, PriorArtSearchResult
from patent_copilot.core.text import tokenize


class ManualPatentAdapter(PatentDataAdapter):
    def __init__(self, documents: list[PriorArtDocument] | None = None) -> None:
        self._documents = {document.id: document for document in documents or []}

    async def search_prior_art(
        self,
        query: str,
        *,
        jurisdiction: str | None = None,
        date_before: str | None = None,
        limit: int = 10,
    ) -> list[PriorArtSearchResult]:
        query_terms = set(tokenize(query))
        results: list[PriorArtSearchResult] = []
        for document in self._documents.values():
            haystack = " ".join(text for _, text in document.searchable_sections())
            overlap = query_terms.intersection(tokenize(haystack))
            if not overlap:
                continue
            results.append(
                PriorArtSearchResult(
                    id=document.id,
                    title=document.title,
                    abstract=document.abstract,
                    jurisdiction=jurisdiction,
                    url=document.url,
                    reason=f"Manual document matched query terms: {', '.join(sorted(overlap)[:6])}.",
                    score=len(overlap) / max(len(query_terms), 1),
                )
            )
        results.sort(key=lambda item: item.score or 0, reverse=True)
        return results[:limit]

    async def fetch_documents(self, ids: list[str]) -> list[PriorArtDocument]:
        return [self._documents[item] for item in ids if item in self._documents]

