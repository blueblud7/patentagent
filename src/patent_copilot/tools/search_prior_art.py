from __future__ import annotations

from datetime import date

import httpx

from patent_copilot.adapters.google_patents import GooglePatentsAdapter
from patent_copilot.adapters.patentsview import PatentsViewAdapter
from patent_copilot.contracts import MCP_RESPONSE_SCHEMA_VERSION


async def search_prior_art_mcp_response(
    query: str,
    jurisdiction: str = "US",
    date_before: str | None = None,
    limit: int = 10,
) -> dict:
    try:
        payload = await search_prior_art_tool(
            query=query,
            jurisdiction=jurisdiction,
            date_before=date_before,
            limit=limit,
        )
    except (TypeError, ValueError) as exc:
        return {
            "ok": False,
            "schema_version": MCP_RESPONSE_SCHEMA_VERSION,
            "error": {
                "code": "invalid_request",
                "message": str(exc),
                "recoverable": True,
                "next_steps": ["Use jurisdiction='US' for v0.1 search or provide prior_art_ids directly."],
            },
        }
    except Exception as exc:  # noqa: BLE001 - keep MCP boundary failures structured.
        return {
            "ok": False,
            "schema_version": MCP_RESPONSE_SCHEMA_VERSION,
            "error": {
                "code": "internal_error",
                "message": f"Unexpected search_prior_art failure: {type(exc).__name__}: {exc}",
                "recoverable": False,
                "next_steps": [
                    "Retry with the same request after checking server logs.",
                    "Run patent-copilot-release-check before deploying this build.",
                ],
            },
        }
    payload["ok"] = True
    payload["schema_version"] = MCP_RESPONSE_SCHEMA_VERSION
    return payload


async def search_prior_art_tool(
    query: str,
    jurisdiction: str = "US",
    date_before: str | None = None,
    limit: int = 10,
) -> dict:
    if not isinstance(query, str):
        raise TypeError("query must be a string for search_prior_art.")
    if not query.strip():
        raise ValueError("query is required for search_prior_art.")
    if not isinstance(jurisdiction, str):
        raise TypeError("jurisdiction must be a string for search_prior_art.")
    if jurisdiction.upper() != "US":
        raise ValueError("v0.1 currently implements live API search for US documents only.")
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise TypeError("limit must be an integer for search_prior_art.")
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100 for search_prior_art.")
    if date_before:
        _validate_date_before(date_before)

    provider = "patentsview"
    warnings: list[str] = []
    try:
        adapter = PatentsViewAdapter()
        results = await adapter.search_prior_art(
            query,
            jurisdiction=jurisdiction,
            date_before=date_before,
            limit=limit,
        )
    except (RuntimeError, httpx.HTTPError) as exc:
        provider = "google_patents"
        warnings.append(
            "PatentsView search unavailable; returned keyless fallback guidance instead. "
            f"Reason: {exc}"
        )
        results = await GooglePatentsAdapter().search_prior_art(
            query,
            jurisdiction=jurisdiction,
            date_before=date_before,
            limit=limit,
        )
    return {
        "provider": provider,
        "results": [item.model_dump(mode="json") for item in results],
        "warnings": warnings,
    }


def _validate_date_before(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("date_before must be a YYYY-MM-DD string.")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date_before must use YYYY-MM-DD format.") from exc
