import asyncio

import httpx

from patent_copilot.adapters.base import PartialPatentFetchError
from patent_copilot.core.schemas import PriorArtDocument, PriorArtSearchResult
from patent_copilot.tools import build_claim_chart as build_claim_chart_module
from patent_copilot.tools.build_claim_chart import (
    _fetch_documents_with_attempts,
    build_claim_chart_mcp_response,
    build_claim_chart_tool,
)


class FakeAdapter:
    def __init__(
        self,
        documents: list[PriorArtDocument] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.documents = documents or []
        self.error = error
        self.requested_ids: list[str] = []

    async def search_prior_art(
        self,
        query: str,
        *,
        jurisdiction: str | None = None,
        date_before: str | None = None,
        limit: int = 10,
    ) -> list[PriorArtSearchResult]:
        return []

    async def fetch_documents(self, ids: list[str]) -> list[PriorArtDocument]:
        self.requested_ids = ids
        if self.error is not None:
            raise self.error
        return self.documents


def test_fetch_documents_falls_back_only_for_missing_ids() -> None:
    primary = FakeAdapter([PriorArtDocument(id="US1111111B2", title="Primary hit")])
    fallback = FakeAdapter([PriorArtDocument(id="US2222222B2", title="Fallback hit")])

    documents, attempts = asyncio.run(
        _fetch_documents_with_attempts(
            ["US1111111B2", "US2222222B2"],
            providers=[primary, fallback],
        )
    )

    assert [document.id for document in documents] == ["US1111111B2", "US2222222B2"]
    assert [attempt.status for attempt in attempts] == ["partial", "complete"]
    assert primary.requested_ids == ["US1111111B2", "US2222222B2"]
    assert fallback.requested_ids == ["US2222222B2"]


def test_fetch_documents_falls_back_for_primary_runtime_failure() -> None:
    primary = FakeAdapter(error=RuntimeError("missing API key"))
    fallback = FakeAdapter([PriorArtDocument(id="US3333333B2", title="Fallback hit")])

    documents, attempts = asyncio.run(
        _fetch_documents_with_attempts(
            ["US3333333B2"],
            providers=[primary, fallback],
        )
    )

    assert [document.id for document in documents] == ["US3333333B2"]
    assert [attempt.status for attempt in attempts] == ["error", "complete"]
    assert fallback.requested_ids == ["US3333333B2"]


def test_fetch_documents_falls_back_for_primary_http_failure() -> None:
    primary = FakeAdapter(error=httpx.ConnectError("network unavailable"))
    fallback = FakeAdapter([PriorArtDocument(id="US4444444B2", title="Fallback hit")])

    documents, attempts = asyncio.run(
        _fetch_documents_with_attempts(
            ["US4444444B2"],
            providers=[primary, fallback],
        )
    )

    assert [document.id for document in documents] == ["US4444444B2"]
    assert [attempt.status for attempt in attempts] == ["error", "complete"]
    assert fallback.requested_ids == ["US4444444B2"]


def test_fetch_documents_requires_every_requested_id_after_fallback() -> None:
    primary = FakeAdapter([PriorArtDocument(id="US5555555B2", title="Primary hit")])
    fallback = FakeAdapter([])

    try:
        asyncio.run(
            _fetch_documents_with_attempts(
                ["US5555555B2", "US6666666B2"],
                providers=[primary, fallback],
            )
        )
    except ValueError as exc:
        assert "US6666666B2" in str(exc)
    else:
        raise AssertionError("missing fallback document should raise ValueError")


def test_fetch_documents_reports_provider_attempts() -> None:
    primary = FakeAdapter([PriorArtDocument(id="US7777777B2", title="Primary hit")])
    fallback = FakeAdapter([PriorArtDocument(id="US8888888B2", title="Fallback hit")])

    documents, attempts = asyncio.run(
        _fetch_documents_with_attempts(
            ["US7777777B2", "US8888888B2"],
            providers=[primary, fallback],
        )
    )

    assert [document.id for document in documents] == ["US7777777B2", "US8888888B2"]
    assert [attempt.status for attempt in attempts] == ["partial", "complete"]
    assert attempts[0].requested_ids == ["US7777777B2", "US8888888B2"]
    assert attempts[0].missing_ids == ["US8888888B2"]
    assert attempts[1].requested_ids == ["US8888888B2"]


def test_fetch_documents_keeps_partial_provider_success_with_error_detail() -> None:
    partial_document = PriorArtDocument(id="US9999991B2", title="Partial hit")
    primary = FakeAdapter(
        error=PartialPatentFetchError(
            "one fallback page failed",
            documents=[partial_document],
            errors={"US9999992B2": "not found"},
        )
    )
    fallback = FakeAdapter([PriorArtDocument(id="US9999992B2", title="Second hit")])

    documents, attempts = asyncio.run(
        _fetch_documents_with_attempts(
            ["US9999991B2", "US9999992B2"],
            providers=[primary, fallback],
        )
    )

    assert [document.id for document in documents] == ["US9999991B2", "US9999992B2"]
    assert [attempt.status for attempt in attempts] == ["partial", "complete"]
    assert attempts[0].found_ids == ["US9999991B2"]
    assert attempts[0].missing_ids == ["US9999992B2"]
    assert attempts[0].error == "one fallback page failed"
    assert fallback.requested_ids == ["US9999992B2"]


def test_build_claim_chart_tool_includes_retrieval_attempts_for_id_fetch() -> None:
    # Use direct prior_art_texts for one ID and verify only the missing ID is fetched.
    payload = asyncio.run(
        build_claim_chart_tool(
            claim_text="1. A system comprising: a processor configured to receive sensor data.",
            prior_art_ids=["US-DEMO-1"],
            prior_art_texts=[
                {
                    "id": "US-DEMO-1",
                    "title": "Sensor system",
                    "description": "A processor receives sensor data.",
                }
            ],
        )
    )

    assert payload["retrieval_attempts"] == []
    assert payload["document_coverage"][0]["source"] == "manual"


def test_fetch_documents_fetches_each_missing_id_once() -> None:
    class DuplicateTrackingAdapter(FakeAdapter):
        async def fetch_documents(self, ids: list[str]) -> list[PriorArtDocument]:
            self.requested_ids = ids
            return [
                PriorArtDocument(
                    id="US1212121B2",
                    title="Duplicate-safe fetch",
                    description="A processor receives sensor data.",
                )
            ]

    adapter = DuplicateTrackingAdapter()

    documents, _ = asyncio.run(
        _fetch_documents_with_attempts(
            ["US1212121B2", "US1212121B2"],
            providers=[adapter],
        )
    )

    assert adapter.requested_ids == ["US1212121B2"]
    assert [document.id for document in documents] == ["US1212121B2"]


def test_build_claim_chart_mcp_success_contract() -> None:
    payload = asyncio.run(
        build_claim_chart_mcp_response(
            claim_text="1. A system comprising: a processor configured to receive sensor data.",
            prior_art_texts=[
                {
                    "id": "US-DEMO-1",
                    "description": "A processor receives sensor data.",
                }
            ],
        )
    )

    assert payload["ok"] is True
    assert payload["schema_version"] == "1.0"
    assert {
        "claim_text",
        "rows",
        "review_summary",
        "markdown",
        "csv",
        "document_coverage",
        "retrieval_attempts",
        "warnings",
    }.issubset(payload)
    assert payload["review_summary"]["total_rows"] == len(payload["rows"])
    assert "review_flag_counts" in payload["review_summary"]
    evidence = payload["rows"][1]["evidence"][0]
    assert {"matched_terms", "missing_terms", "term_coverage"}.issubset(evidence)


def test_build_claim_chart_mcp_response_returns_structured_invalid_request() -> None:
    payload = asyncio.run(
        build_claim_chart_mcp_response(
            claim_text=" ",
            prior_art_texts=[{"id": "US-DEMO-1", "description": "A processor receives data."}],
        )
    )

    assert payload["ok"] is False
    assert payload["schema_version"] == "1.0"
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["recoverable"] is True


def test_build_claim_chart_mcp_response_rejects_non_string_claim_text() -> None:
    payload = asyncio.run(
        build_claim_chart_mcp_response(
            claim_text=123,  # type: ignore[arg-type]
            prior_art_texts=[{"id": "US-DEMO-1", "description": "A processor receives data."}],
        )
    )

    assert payload["ok"] is False
    assert payload["schema_version"] == "1.0"
    assert payload["error"]["code"] == "invalid_request"
    assert "claim_text must be a string" in payload["error"]["message"]


def test_build_claim_chart_mcp_response_rejects_empty_patent_ids() -> None:
    payload = asyncio.run(
        build_claim_chart_mcp_response(
            claim_text="1. A system comprising: a processor.",
            prior_art_ids=[""],
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "prior_art_ids" in payload["error"]["message"]


def test_build_claim_chart_mcp_response_rejects_non_list_patent_ids() -> None:
    payload = asyncio.run(
        build_claim_chart_mcp_response(
            claim_text="1. A system comprising: a processor.",
            prior_art_ids="US1234567B2",  # type: ignore[arg-type]
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "prior_art_ids must be a list" in payload["error"]["message"]


def test_build_claim_chart_mcp_response_rejects_non_string_patent_id() -> None:
    payload = asyncio.run(
        build_claim_chart_mcp_response(
            claim_text="1. A system comprising: a processor.",
            prior_art_ids=[123],  # type: ignore[list-item]
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "prior_art_ids[0] must be a string" in payload["error"]["message"]


def test_build_claim_chart_mcp_response_rejects_non_list_prior_art_texts() -> None:
    payload = asyncio.run(
        build_claim_chart_mcp_response(
            claim_text="1. A system comprising: a processor.",
            prior_art_texts={"id": "US-DEMO-1"},  # type: ignore[arg-type]
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "prior_art_texts must be a list" in payload["error"]["message"]


def test_build_claim_chart_mcp_response_rejects_combined_reference_limit() -> None:
    payload = asyncio.run(
        build_claim_chart_mcp_response(
            claim_text="1. A system comprising: a processor.",
            prior_art_ids=[f"US120000{index:02d}B2" for index in range(13)],
            prior_art_texts=[
                {
                    "id": f"US-DEMO-{index}",
                    "description": "A processor receives data.",
                }
                for index in range(13)
            ],
        )
    )

    assert payload["ok"] is False
    assert payload["schema_version"] == "1.0"
    assert payload["error"]["code"] == "invalid_request"
    assert "at most 25 prior-art references" in payload["error"]["message"]


def test_build_claim_chart_mcp_response_rejects_missing_manual_document_id() -> None:
    payload = asyncio.run(
        build_claim_chart_mcp_response(
            claim_text="1. A system comprising: a processor.",
            prior_art_texts=[{"description": "A processor receives data."}],
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "id must be a non-empty string" in payload["error"]["message"]


def test_build_claim_chart_mcp_response_rejects_manual_document_without_text() -> None:
    payload = asyncio.run(
        build_claim_chart_mcp_response(
            claim_text="1. A system comprising: a processor.",
            prior_art_texts=[{"id": "US-DEMO-1"}],
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "at least one text field" in payload["error"]["message"]


def test_build_claim_chart_mcp_response_rejects_too_many_references() -> None:
    payload = asyncio.run(
        build_claim_chart_mcp_response(
            claim_text="1. A system comprising: a processor.",
            prior_art_ids=[f"US{i:07d}B2" for i in range(26)],
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "at most 25 prior-art references" in payload["error"]["message"]


def test_build_claim_chart_mcp_response_returns_structured_internal_error(monkeypatch) -> None:
    async def raise_unexpected(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(build_claim_chart_module, "build_claim_chart_tool", raise_unexpected)

    payload = asyncio.run(
        build_claim_chart_module.build_claim_chart_mcp_response(
            claim_text="1. A system comprising: a processor.",
            prior_art_texts=[{"id": "US-DEMO-1", "description": "A processor receives data."}],
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["recoverable"] is False
