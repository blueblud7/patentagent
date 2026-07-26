from __future__ import annotations

import asyncio
from typing import Any

import httpx

from patent_copilot.adapters.patentsview import PatentsViewAdapter, _raise_for_status


class FakePatentsViewAdapter(PatentsViewAdapter):
    def __init__(self) -> None:
        super().__init__(api_key="test-key", base_url="https://example.test")
        self.paths: list[str] = []

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.paths.append(path)
        if path == "/patent/":
            return {
                "patents": [
                    {
                        "patent_id": "1234567",
                        "patent_title": "Sensor classifier",
                        "patent_abstract": "A sensor classifier uses a processor.",
                    }
                ]
            }
        if path == "/publication/":
            return {
                "publications": [
                    {
                        "document_number": "20240370584",
                        "publication_title": "AI data loss prevention",
                        "publication_abstract": "A system prevents data loss when using AI tools.",
                        "publication_date": "2024-11-07",
                    }
                ]
            }
        if path == "/g_claim/":
            return {
                "g_claims": [
                    {
                        "patent_id": "1234567",
                        "claim_sequence": 1,
                        "claim_number": "00002",
                        "claim_text": "The system of claim 1, wherein memory stores instructions.",
                    },
                    {
                        "patent_id": "1234567",
                        "claim_sequence": 0,
                        "claim_number": "00001",
                        "claim_text": "A system comprising a processor receiving sensor data.",
                    },
                ]
            }
        if path == "/g_detail_desc_text/":
            return {
                "g_detail_desc_texts": [
                    {
                        "patent_id": "1234567",
                        "description_text": (
                            "[0042] The processor receives sensor data. "
                            "[0043] Memory stores classifier instructions."
                        ),
                    }
                ]
            }
        if path == "/g_brf_sum_text/":
            return {
                "g_brf_sum_texts": [
                    {
                        "patent_id": "1234567",
                        "summary_text": "A brief summary should be secondary to detail text.",
                    }
                ]
            }
        if path == "/pg_claim/":
            return {
                "pg_claims": [
                    {
                        "document_number": "20240370584",
                        "claim_sequence": 0,
                        "claim_number": "00001",
                        "claim_text": "A system comprising a policy engine for data loss prevention.",
                    }
                ]
            }
        if path == "/pg_detail_desc_text/":
            return {
                "pg_detail_desc_texts": [
                    {
                        "document_number": "20240370584",
                        "description_text": "[0004] The policy engine blocks sensitive data.",
                    }
                ]
            }
        if path == "/pg_brf_sum_text/":
            return {
                "pg_brf_sum_texts": [
                    {
                        "document_number": "20240370584",
                        "summary_text": "A fallback summary for data loss prevention.",
                    }
                ]
            }
        return {}


class FakeOptionalFailurePatentsViewAdapter(FakePatentsViewAdapter):
    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if path == "/g_claim/":
            self.paths.append(path)
            raise RuntimeError("PatentsView request failed for /g_claim/: HTTP 503.")
        return await super()._post(path, payload)


def test_patentsview_fetch_documents_enriches_with_text_endpoints() -> None:
    adapter = FakePatentsViewAdapter()

    documents = asyncio.run(adapter.fetch_documents(["US1234567B2"]))

    assert adapter.paths == ["/patent/", "/g_claim/", "/g_detail_desc_text/", "/g_brf_sum_text/"]
    assert len(documents) == 1
    document = documents[0]
    assert document.id == "US1234567B2"
    assert document.title == "Sensor classifier"
    assert document.abstract == "A sensor classifier uses a processor."
    assert document.claims is not None
    assert document.claims.index("Claim 00001") < document.claims.index("Claim 00002")
    assert "[0042] The processor receives sensor data." in (document.description or "")
    assert document.metadata["text_sources"] == [
        "patent",
        "g_claim",
        "g_detail_desc_text",
    ]


def test_patentsview_adapter_treats_blank_api_key_as_missing(monkeypatch) -> None:
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "   ")
    adapter = PatentsViewAdapter()

    try:
        asyncio.run(adapter.fetch_documents(["US1234567B2"]))
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("blank PATENTSVIEW_API_KEY should be treated as missing")

    assert "PATENTSVIEW_API_KEY is not configured" in message


def test_patentsview_fetch_documents_records_optional_endpoint_errors() -> None:
    adapter = FakeOptionalFailurePatentsViewAdapter()

    documents = asyncio.run(adapter.fetch_documents(["US1234567B2"]))

    assert len(documents) == 1
    document = documents[0]
    assert document.claims is None
    assert document.description
    assert document.metadata["optional_endpoint_errors"] == [
        {
            "endpoint": "/g_claim/",
            "error": "PatentsView request failed for /g_claim/: HTTP 503.",
        }
    ]


def test_patentsview_optional_errors_do_not_leak_between_record_types() -> None:
    adapter = FakeOptionalFailurePatentsViewAdapter()

    documents = asyncio.run(adapter.fetch_documents(["US1234567B2", "US20240370584A1"]))

    by_id = {document.id: document for document in documents}
    assert "optional_endpoint_errors" in by_id["US1234567B2"].metadata
    assert "optional_endpoint_errors" not in by_id["US20240370584A1"].metadata


def test_patentsview_fetch_documents_preserves_requested_mixed_record_order() -> None:
    adapter = FakePatentsViewAdapter()

    documents = asyncio.run(adapter.fetch_documents(["US20240370584A1", "US1234567B2"]))

    assert [document.id for document in documents] == ["US20240370584A1", "US1234567B2"]


def test_patentsview_fetch_documents_enriches_publication_text_endpoints() -> None:
    adapter = FakePatentsViewAdapter()

    documents = asyncio.run(adapter.fetch_documents(["US20240370584A1"]))

    assert adapter.paths == [
        "/publication/",
        "/pg_claim/",
        "/pg_detail_desc_text/",
        "/pg_brf_sum_text/",
    ]
    assert len(documents) == 1
    document = documents[0]
    assert document.id == "US20240370584A1"
    assert document.title == "AI data loss prevention"
    assert "policy engine" in (document.claims or "")
    assert "[0004] The policy engine blocks sensitive data." in (document.description or "")
    assert document.metadata["record_type"] == "publication"
    assert document.metadata["text_sources"] == [
        "publication",
        "pg_claim",
        "pg_detail_desc_text",
    ]


def test_patentsview_http_errors_include_endpoint_status_and_body() -> None:
    response = httpx.Response(
        429,
        headers={"Retry-After": "60"},
        request=httpx.Request("POST", "https://example.test/api/v1/patent/"),
        text='{"error": "rate limit exceeded"}',
    )

    try:
        _raise_for_status(response, "/patent/")
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("HTTP status error should raise RuntimeError")

    assert "/patent/" in message
    assert "HTTP 429" in message
    assert "rate limit exceeded" in message
    assert "PatentsView rate limit exceeded" in message
    assert "Retry after 60 seconds" in message


def test_patentsview_403_errors_include_key_guidance() -> None:
    response = httpx.Response(
        403,
        request=httpx.Request("POST", "https://example.test/api/v1/patent/"),
        text='{"error": "forbidden"}',
    )

    try:
        _raise_for_status(response, "/patent/")
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("HTTP status error should raise RuntimeError")

    assert "PATENTSVIEW_API_KEY" in message
    assert "X-Api-Key" in message
