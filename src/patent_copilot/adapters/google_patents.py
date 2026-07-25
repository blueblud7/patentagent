from __future__ import annotations

from html.parser import HTMLParser

from patent_copilot.adapters.base import PatentDataAdapter
from patent_copilot.core.patent_id import google_patents_url, normalize_patent_id
from patent_copilot.core.schemas import PriorArtDocument, PriorArtSearchResult
from patent_copilot.core.text import normalize_space, tokenize


class GooglePatentsAdapter(PatentDataAdapter):
    """Keyless document fetch adapter for Google Patents pages.

    This is intended as a pragmatic v0.1 fallback for patent-ID based claim charts.
    It is not a bulk search adapter.
    """

    async def search_prior_art(
        self,
        query: str,
        *,
        jurisdiction: str | None = None,
        date_before: str | None = None,
        limit: int = 10,
    ) -> list[PriorArtSearchResult]:
        terms = ", ".join(tokenize(query)[:8]) or query
        return [
            PriorArtSearchResult(
                id="manual-search-required",
                title="Google Patents fallback does not provide full-text search",
                jurisdiction=jurisdiction,
                reason=(
                    "Provide specific prior_art_ids or configure PATENTSVIEW_API_KEY for API search. "
                    f"Query terms parsed for manual search: {terms}."
                ),
            )
        ][:limit]

    async def fetch_documents(self, ids: list[str]) -> list[PriorArtDocument]:
        documents: list[PriorArtDocument] = []
        for patent_id in ids:
            normalized = normalize_patent_id(patent_id)
            html = await self._fetch_html(google_patents_url(normalized))
            documents.append(parse_google_patents_html(html, normalized))
        return documents

    async def _fetch_html(self, url: str) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "Fetching patent IDs requires httpx. Install with `pip install -e .`, "
                "or pass prior_art_texts directly for offline operation."
            ) from exc

        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "patent-copilot/0.1"})
            response.raise_for_status()
            return response.text


def parse_google_patents_html(html: str, patent_id: str) -> PriorArtDocument:
    parser = _GooglePatentsHTMLParser()
    parser.feed(html)
    title = parser.first_text("title")
    abstract = parser.first_text("abstract")
    claims = parser.join_text("claims")
    description = parser.join_text("description")

    return PriorArtDocument(
        id=normalize_patent_id(patent_id),
        title=title,
        abstract=abstract,
        claims=claims,
        description=description,
        url=google_patents_url(patent_id),
        metadata={"source": "google_patents"},
    )


class _GooglePatentsHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._stack: list[tuple[str, str]] = []
        self._buffers: dict[str, list[str]] = {
            "title": [],
            "abstract": [],
            "claims": [],
            "description": [],
        }

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {name: value for name, value in attrs}
        section = None
        if tag == "meta" and attr.get("name") == "DC.title" and attr.get("content"):
            self._buffers["title"].append(attr["content"] or "")
            return
        if attr.get("class") and "abstract" in attr["class"]:
            section = "abstract"
        elif attr.get("class") and "claim-text" in attr["class"]:
            section = "claims"
        elif attr.get("class") and "description" in attr["class"]:
            section = "description"
        elif attr.get("itemprop") == "title":
            section = "title"
        elif attr.get("itemprop") == "abstract":
            section = "abstract"
        elif attr.get("itemprop") == "claims":
            section = "claims"
        elif attr.get("itemprop") == "description":
            section = "description"

        if section:
            self._stack.append((section, tag))

    def handle_endtag(self, tag: str) -> None:
        if self._stack and self._stack[-1][1] == tag:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._stack:
            return
        text = normalize_space(data)
        if text:
            self._buffers[self._stack[-1][0]].append(text)

    def first_text(self, section: str) -> str | None:
        values = [item for item in self._buffers.get(section, []) if item]
        return values[0] if values else None

    def join_text(self, section: str) -> str | None:
        values = [item for item in self._buffers.get(section, []) if item]
        if not values:
            return None
        return normalize_space(" ".join(values))
