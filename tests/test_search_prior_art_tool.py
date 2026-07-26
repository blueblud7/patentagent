import asyncio

from patent_copilot.tools import search_prior_art as search_prior_art_module
from patent_copilot.tools.search_prior_art import (
    search_prior_art_mcp_response,
    search_prior_art_tool,
)


def test_search_prior_art_tool_returns_keyless_fallback_guidance_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)

    payload = asyncio.run(search_prior_art_tool("sensor processor memory"))

    assert payload["provider"] == "google_patents"
    assert payload["results"]
    assert payload["warnings"]
    assert payload["results"][0]["id"] == "manual-search-required"


def test_search_prior_art_mcp_response_returns_structured_invalid_request() -> None:
    payload = asyncio.run(search_prior_art_mcp_response("", jurisdiction="EP"))

    assert payload["ok"] is False
    assert payload["schema_version"] == "1.0"
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["recoverable"] is True


def test_search_prior_art_rejects_out_of_range_limit() -> None:
    payload = asyncio.run(search_prior_art_mcp_response("sensor", limit=0))

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "limit must be between 1 and 100" in payload["error"]["message"]


def test_search_prior_art_rejects_non_integer_limit() -> None:
    payload = asyncio.run(search_prior_art_mcp_response("sensor", limit="10"))  # type: ignore[arg-type]

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "limit must be an integer" in payload["error"]["message"]


def test_search_prior_art_rejects_invalid_date_before() -> None:
    payload = asyncio.run(search_prior_art_mcp_response("sensor", date_before="2024-99-99"))

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "YYYY-MM-DD" in payload["error"]["message"]


def test_search_prior_art_rejects_non_string_query() -> None:
    payload = asyncio.run(search_prior_art_mcp_response(123))  # type: ignore[arg-type]

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_request"
    assert "query must be a string" in payload["error"]["message"]


def test_search_prior_art_mcp_success_contract(monkeypatch) -> None:
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)

    payload = asyncio.run(search_prior_art_mcp_response("sensor processor memory"))

    assert payload["ok"] is True
    assert payload["schema_version"] == "1.0"
    assert {"provider", "results", "warnings"}.issubset(payload)
    assert isinstance(payload["results"], list)
    assert isinstance(payload["warnings"], list)


def test_search_prior_art_mcp_response_returns_structured_internal_error(monkeypatch) -> None:
    async def raise_unexpected(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(search_prior_art_module, "search_prior_art_tool", raise_unexpected)

    payload = asyncio.run(search_prior_art_module.search_prior_art_mcp_response("sensor"))

    assert payload["ok"] is False
    assert payload["schema_version"] == "1.0"
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["recoverable"] is False
