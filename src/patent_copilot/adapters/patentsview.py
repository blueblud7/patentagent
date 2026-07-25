from __future__ import annotations

import os
from typing import Any

from patent_copilot.adapters.base import PatentDataAdapter
from patent_copilot.core.patent_id import google_patents_url, patentsview_numeric_id
from patent_copilot.core.schemas import PriorArtDocument, PriorArtSearchResult


PATENTSVIEW_BASE_URL = "https://search.patentsview.org/api/v1"


class PatentsViewAdapter(PatentDataAdapter):
    def __init__(self, api_key: str | None = None, base_url: str = PATENTSVIEW_BASE_URL) -> None:
        self.api_key = api_key or os.getenv("PATENTSVIEW_API_KEY")
        self.base_url = base_url.rstrip("/")

    async def search_prior_art(
        self,
        query: str,
        *,
        jurisdiction: str | None = "US",
        date_before: str | None = None,
        limit: int = 10,
    ) -> list[PriorArtSearchResult]:
        self._require_api_key()
        filters: list[dict[str, Any]] = [
            {
                "_or": [
                    {"patent_title": {"_text_any": query}},
                    {"patent_abstract": {"_text_any": query}},
                ]
            }
        ]
        if date_before:
            filters.append({"patent_date": {"_lt": date_before}})

        payload = {
            "q": {"_and": filters} if len(filters) > 1 else filters[0],
            "f": ["patent_id", "patent_title", "patent_abstract", "patent_date"],
            "o": {"size": min(limit, 100)},
        }
        data = await self._post("/patent/", payload)
        patents = data.get("patents", [])
        return [
            PriorArtSearchResult(
                id=item.get("patent_id", ""),
                title=item.get("patent_title"),
                abstract=item.get("patent_abstract"),
                publication_date=item.get("patent_date"),
                jurisdiction=jurisdiction,
                url=google_patents_url(item.get("patent_id")),
                reason="Matched query against PatentsView title or abstract fields.",
            )
            for item in patents
            if item.get("patent_id")
        ]

    async def fetch_documents(self, ids: list[str]) -> list[PriorArtDocument]:
        self._require_api_key()
        if not ids:
            return []

        normalized_ids = [patentsview_numeric_id(item) for item in ids]
        payload = {
            "q": {"patent_id": {"_in": normalized_ids}},
            "f": ["patent_id", "patent_title", "patent_abstract"],
            "o": {"size": min(len(ids), 100)},
        }
        data = await self._post("/patent/", payload)
        documents: list[PriorArtDocument] = []
        for item in data.get("patents", []):
            patent_id = item.get("patent_id")
            if not patent_id:
                continue
            documents.append(
                PriorArtDocument(
                    id=patent_id,
                    title=item.get("patent_title"),
                    abstract=item.get("patent_abstract"),
                    url=google_patents_url(patent_id),
                    metadata={"source": "patentsview"},
                )
            )
        return documents

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "The PatentsView adapter requires httpx. Install the package with `pip install -e .`."
            ) from exc

        headers = {"X-Api-Key": self.api_key or ""}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.base_url}{path}", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "PATENTSVIEW_API_KEY is not configured. Pass prior_art_texts directly or set the key."
            )
