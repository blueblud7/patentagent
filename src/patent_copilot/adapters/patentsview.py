from __future__ import annotations

from typing import Any

import httpx

from patent_copilot.adapters.base import PatentDataAdapter
from patent_copilot.config import clean_env_value, get_env_value
from patent_copilot.core.patent_id import (
    google_patents_url,
    is_us_publication_id,
    normalize_patent_id,
    patentsview_numeric_id,
)
from patent_copilot.core.schemas import PriorArtDocument, PriorArtSearchResult
from patent_copilot.core.text import normalize_space

PATENTSVIEW_BASE_URL = "https://search.patentsview.org/api/v1"


class PatentsViewAdapter(PatentDataAdapter):
    def __init__(self, api_key: str | None = None, base_url: str = PATENTSVIEW_BASE_URL) -> None:
        self.api_key = clean_env_value(api_key) or get_env_value("PATENTSVIEW_API_KEY")
        self.base_url = base_url.rstrip("/")
        self._optional_endpoint_errors: list[dict[str, str]] = []

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
        self._optional_endpoint_errors = []

        grant_numbers: list[str] = []
        publication_numbers: list[str] = []
        requested_by_number: dict[str, str] = {}
        for item in ids:
            normalized = normalize_patent_id(item)
            number = patentsview_numeric_id(normalized)
            requested_by_number[number] = normalized
            if is_us_publication_id(normalized):
                publication_numbers.append(number)
            else:
                grant_numbers.append(number)

        documents: list[PriorArtDocument] = []
        documents.extend(await self._fetch_grant_documents(grant_numbers, requested_by_number))
        documents.extend(await self._fetch_publication_documents(publication_numbers, requested_by_number))
        return _order_documents_by_requested_ids(ids, documents)

    async def _fetch_grant_documents(
        self,
        patent_ids: list[str],
        requested_by_number: dict[str, str],
    ) -> list[PriorArtDocument]:
        if not patent_ids:
            return []

        payload = {
            "q": {"patent_id": {"_in": patent_ids}},
            "f": ["patent_id", "patent_title", "patent_abstract"],
            "o": {"size": min(len(patent_ids), 100)},
        }
        data = await self._post("/patent/", payload)
        optional_error_start = len(self._optional_endpoint_errors)
        claims_by_id = await self._fetch_claims(patent_ids)
        descriptions_by_id = await self._fetch_description_texts(patent_ids)
        summaries_by_id = await self._fetch_summary_texts(patent_ids)
        optional_errors = self._optional_endpoint_errors[optional_error_start:]

        documents: list[PriorArtDocument] = []
        for item in data.get("patents", []):
            patent_id = item.get("patent_id")
            if not patent_id:
                continue
            claims = claims_by_id.get(patent_id)
            description = descriptions_by_id.get(patent_id) or summaries_by_id.get(patent_id)
            text_sources = ["patent"]
            if claims:
                text_sources.append("g_claim")
            if descriptions_by_id.get(patent_id):
                text_sources.append("g_detail_desc_text")
            elif summaries_by_id.get(patent_id):
                text_sources.append("g_brf_sum_text")
            documents.append(
                PriorArtDocument(
                    id=requested_by_number.get(patent_id, normalize_patent_id(f"US{patent_id}")),
                    title=item.get("patent_title"),
                    abstract=item.get("patent_abstract"),
                    claims=claims,
                    description=description,
                    url=google_patents_url(patent_id),
                    metadata={
                        "source": "patentsview",
                        "text_sources": text_sources,
                        **_optional_errors_metadata(optional_errors),
                    },
                )
            )
        return documents

    async def _fetch_publication_documents(
        self,
        document_numbers: list[str],
        requested_by_number: dict[str, str],
    ) -> list[PriorArtDocument]:
        if not document_numbers:
            return []

        payload = {
            "q": {"document_number": {"_in": document_numbers}},
            "f": ["document_number", "publication_title", "publication_abstract", "publication_date"],
            "o": {"size": min(len(document_numbers), 100)},
        }
        data = await self._post("/publication/", payload)
        optional_error_start = len(self._optional_endpoint_errors)
        claims_by_id = await self._fetch_publication_claims(document_numbers)
        descriptions_by_id = await self._fetch_publication_description_texts(document_numbers)
        summaries_by_id = await self._fetch_publication_summary_texts(document_numbers)
        optional_errors = self._optional_endpoint_errors[optional_error_start:]

        documents: list[PriorArtDocument] = []
        for item in data.get("publications", []):
            document_number = item.get("document_number")
            if not document_number:
                continue
            claims = claims_by_id.get(document_number)
            description = descriptions_by_id.get(document_number) or summaries_by_id.get(document_number)
            text_sources = ["publication"]
            if claims:
                text_sources.append("pg_claim")
            if descriptions_by_id.get(document_number):
                text_sources.append("pg_detail_desc_text")
            elif summaries_by_id.get(document_number):
                text_sources.append("pg_brf_sum_text")
            requested_id = requested_by_number.get(document_number, normalize_patent_id(f"US{document_number}A1"))
            documents.append(
                PriorArtDocument(
                    id=requested_id,
                    title=item.get("publication_title"),
                    abstract=item.get("publication_abstract"),
                    claims=claims,
                    description=description,
                    url=google_patents_url(requested_id),
                    metadata={
                        "source": "patentsview",
                        "record_type": "publication",
                        "document_number": document_number,
                        "publication_date": item.get("publication_date"),
                        "text_sources": text_sources,
                        **_optional_errors_metadata(optional_errors),
                    },
                )
            )
        return documents

    async def _fetch_claims(self, patent_ids: list[str]) -> dict[str, str]:
        payload = {
            "q": {"patent_id": {"_in": patent_ids}},
            "f": ["patent_id", "claim_sequence", "claim_number", "claim_text"],
            "s": [{"patent_id": "asc"}, {"claim_sequence": "asc"}],
            "o": {"size": 1000},
        }
        data = await self._post_optional("/g_claim/", payload)
        by_id: dict[str, list[tuple[int, str]]] = {}
        for item in data.get("g_claims", []):
            patent_id = item.get("patent_id")
            claim_text = item.get("claim_text")
            if not patent_id or not claim_text:
                continue
            sequence = _int_or_zero(item.get("claim_sequence"))
            claim_number = item.get("claim_number")
            prefix = f"Claim {claim_number}: " if claim_number else ""
            by_id.setdefault(patent_id, []).append((sequence, normalize_space(prefix + claim_text)))
        return {
            patent_id: normalize_space(" ".join(text for _, text in sorted(items)))
            for patent_id, items in by_id.items()
        }

    async def _fetch_description_texts(self, patent_ids: list[str]) -> dict[str, str]:
        payload = {
            "q": {"patent_id": {"_in": patent_ids}},
            "f": ["patent_id", "description_text", "description_length"],
            "o": {"size": min(len(patent_ids), 1000)},
        }
        data = await self._post_optional("/g_detail_desc_text/", payload)
        return _text_by_patent_id(data.get("g_detail_desc_texts", []), "description_text")

    async def _fetch_summary_texts(self, patent_ids: list[str]) -> dict[str, str]:
        payload = {
            "q": {"patent_id": {"_in": patent_ids}},
            "f": ["patent_id", "summary_text"],
            "o": {"size": min(len(patent_ids), 1000)},
        }
        data = await self._post_optional("/g_brf_sum_text/", payload)
        return _text_by_patent_id(data.get("g_brf_sum_texts", []), "summary_text")

    async def _fetch_publication_claims(self, document_numbers: list[str]) -> dict[str, str]:
        payload = {
            "q": {"document_number": {"_in": document_numbers}},
            "f": ["document_number", "claim_sequence", "claim_number", "claim_text"],
            "s": [{"document_number": "asc"}, {"claim_sequence": "asc"}],
            "o": {"size": 1000},
        }
        data = await self._post_optional("/pg_claim/", payload)
        by_id: dict[str, list[tuple[int, str]]] = {}
        for item in data.get("pg_claims", []):
            document_number = item.get("document_number")
            claim_text = item.get("claim_text")
            if not document_number or not claim_text:
                continue
            sequence = _int_or_zero(item.get("claim_sequence"))
            claim_number = item.get("claim_number")
            prefix = f"Claim {claim_number}: " if claim_number else ""
            by_id.setdefault(document_number, []).append((sequence, normalize_space(prefix + claim_text)))
        return {
            document_number: normalize_space(" ".join(text for _, text in sorted(items)))
            for document_number, items in by_id.items()
        }

    async def _fetch_publication_description_texts(self, document_numbers: list[str]) -> dict[str, str]:
        payload = {
            "q": {"document_number": {"_in": document_numbers}},
            "f": ["document_number", "description_text", "description_length"],
            "o": {"size": min(len(document_numbers), 1000)},
        }
        data = await self._post_optional("/pg_detail_desc_text/", payload)
        return _text_by_patent_id(data.get("pg_detail_desc_texts", []), "description_text", "document_number")

    async def _fetch_publication_summary_texts(self, document_numbers: list[str]) -> dict[str, str]:
        payload = {
            "q": {"document_number": {"_in": document_numbers}},
            "f": ["document_number", "summary_text"],
            "o": {"size": min(len(document_numbers), 1000)},
        }
        data = await self._post_optional("/pg_brf_sum_text/", payload)
        return _text_by_patent_id(data.get("pg_brf_sum_texts", []), "summary_text", "document_number")

    async def _post_optional(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return await self._post(path, payload)
        except (RuntimeError, httpx.HTTPError) as exc:
            self._optional_endpoint_errors.append({"endpoint": path, "error": str(exc)})
            return {}

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
            _raise_for_status(response, path)
            return response.json()

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "PATENTSVIEW_API_KEY is not configured. Pass prior_art_texts directly or set the key."
            )


def _text_by_patent_id(
    items: list[dict[str, Any]],
    field: str,
    id_field: str = "patent_id",
) -> dict[str, str]:
    output: dict[str, str] = {}
    for item in items:
        patent_id = item.get(id_field)
        text = item.get(field)
        if patent_id and text:
            output[patent_id] = normalize_space(text)
    return output


def _order_documents_by_requested_ids(
    requested_ids: list[str],
    documents: list[PriorArtDocument],
) -> list[PriorArtDocument]:
    by_id = {normalize_patent_id(document.id): document for document in documents}
    ordered = []
    for requested_id in requested_ids:
        document = by_id.get(normalize_patent_id(requested_id))
        if document is not None:
            ordered.append(document)
    return ordered


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _raise_for_status(response: httpx.Response, path: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = normalize_space(response.text)[:240]
        detail = f" Body: {body}" if body else ""
        guidance = _http_status_guidance(response)
        raise RuntimeError(
            f"PatentsView request failed for {path}: HTTP {response.status_code}.{detail}{guidance}"
        ) from exc


def _http_status_guidance(response: httpx.Response) -> str:
    if response.status_code == 403:
        return " Check PATENTSVIEW_API_KEY and ensure the request sends the X-Api-Key header."
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        retry_hint = f" Retry after {retry_after} seconds." if retry_after else ""
        return f" PatentsView rate limit exceeded; reduce request rate.{retry_hint}"
    if response.status_code >= 500:
        return " PatentsView service returned a server error; retry later or use manual prior_art_texts."
    return ""


def _optional_errors_metadata(errors: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    return {"optional_endpoint_errors": list(errors)} if errors else {}
