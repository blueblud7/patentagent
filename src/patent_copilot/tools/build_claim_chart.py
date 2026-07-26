from __future__ import annotations

from patent_copilot.adapters.base import PatentDataAdapter
from patent_copilot.adapters.google_patents import GooglePatentsAdapter
from patent_copilot.adapters.patentsview import PatentsViewAdapter
from patent_copilot.contracts import MAX_PRIOR_ART_REFERENCES, MCP_RESPONSE_SCHEMA_VERSION
from patent_copilot.core.chart_builder import build_claim_chart as build_chart
from patent_copilot.core.patent_id import normalize_patent_id
from patent_copilot.core.schemas import ClaimChart, PriorArtDocument, RetrievalAttempt
from patent_copilot.retrieval import PatentRetrievalError, fetch_documents_from_providers

_TEXT_FIELDS = ("title", "abstract", "claims", "description")


async def build_claim_chart_mcp_response(
    claim_text: str,
    prior_art_ids: list[str] | None = None,
    prior_art_texts: list[dict] | None = None,
) -> dict:
    try:
        payload = await build_claim_chart_tool(
            claim_text=claim_text,
            prior_art_ids=prior_art_ids,
            prior_art_texts=prior_art_texts,
        )
    except PatentRetrievalError as exc:
        return {
            "ok": False,
            "schema_version": MCP_RESPONSE_SCHEMA_VERSION,
            "error": {
                "code": "prior_art_retrieval_failed",
                "message": str(exc),
                "recoverable": True,
                "next_steps": [
                    "Verify the patent IDs.",
                    "Provide prior_art_texts directly.",
                    "Configure PATENTSVIEW_API_KEY or retry later.",
                ],
            },
            "retrieval_attempts": [attempt.model_dump(mode="json") for attempt in exc.attempts],
        }
    except (TypeError, ValueError) as exc:
        return {
            "ok": False,
            "schema_version": MCP_RESPONSE_SCHEMA_VERSION,
            "error": {
                "code": "invalid_request",
                "message": str(exc),
                "recoverable": True,
                "next_steps": [
                    "Provide claim_text and at least one prior_art_texts item or prior_art_ids item."
                ],
            },
        }
    except Exception as exc:  # noqa: BLE001 - keep MCP boundary failures structured.
        return {
            "ok": False,
            "schema_version": MCP_RESPONSE_SCHEMA_VERSION,
            "error": {
                "code": "internal_error",
                "message": f"Unexpected build_claim_chart failure: {type(exc).__name__}: {exc}",
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


async def build_claim_chart_tool(
    claim_text: str,
    prior_art_ids: list[str] | None = None,
    prior_art_texts: list[dict] | None = None,
) -> dict:
    if not isinstance(claim_text, str):
        raise TypeError("claim_text must be a string for build_claim_chart.")
    if not claim_text.strip():
        raise ValueError("claim_text is required for build_claim_chart.")

    documents = _validate_prior_art_texts(prior_art_texts)
    normalized_prior_art_ids = _validate_prior_art_ids(prior_art_ids)
    _validate_reference_count(len(documents), len(normalized_prior_art_ids))
    retrieval_attempts: list[RetrievalAttempt] = []

    known_ids = {normalize_patent_id(doc.id) for doc in documents}
    missing_ids = []
    seen_missing_ids = set()
    for normalized in normalized_prior_art_ids:
        if normalized not in known_ids and normalized not in seen_missing_ids:
            missing_ids.append(normalized)
            seen_missing_ids.add(normalized)
    if missing_ids:
        fetched, retrieval_attempts = await _fetch_documents_with_attempts(missing_ids)
        documents.extend(fetched)

    if not documents:
        raise ValueError(
            "No prior-art documents available. Provide prior_art_texts or configure PATENTSVIEW_API_KEY."
        )

    chart: ClaimChart = build_chart(claim_text, documents)
    chart.retrieval_attempts = retrieval_attempts
    return chart.model_dump(mode="json")


def _validate_prior_art_texts(prior_art_texts: list[dict] | None) -> list[PriorArtDocument]:
    if prior_art_texts is None:
        return []
    if not isinstance(prior_art_texts, list):
        raise TypeError("prior_art_texts must be a list of document objects.")

    documents: list[PriorArtDocument] = []
    for index, item in enumerate(prior_art_texts):
        if not isinstance(item, dict):
            raise TypeError(f"prior_art_texts[{index}] must be an object.")
        if not isinstance(item.get("id"), str) or not item["id"].strip():
            raise ValueError(f"prior_art_texts[{index}].id must be a non-empty string.")
        if not any(isinstance(item.get(field), str) and item[field].strip() for field in _TEXT_FIELDS):
            raise ValueError(
                f"prior_art_texts[{index}] must include at least one text field: "
                f"{', '.join(_TEXT_FIELDS)}."
            )
        documents.append(PriorArtDocument.model_validate(item))
    return documents


def _validate_prior_art_ids(prior_art_ids: list[str] | None) -> list[str]:
    if prior_art_ids is None:
        return []
    if not isinstance(prior_art_ids, list):
        raise TypeError("prior_art_ids must be a list of strings.")

    normalized_ids = []
    for index, item in enumerate(prior_art_ids):
        if not isinstance(item, str):
            raise TypeError(f"prior_art_ids[{index}] must be a string.")
        if not item.strip():
            raise ValueError("prior_art_ids cannot contain empty values.")
        normalized_ids.append(normalize_patent_id(item))
    return normalized_ids


def _validate_reference_count(manual_count: int, id_count: int) -> None:
    total = manual_count + id_count
    if total > MAX_PRIOR_ART_REFERENCES:
        raise ValueError(
            f"build_claim_chart accepts at most {MAX_PRIOR_ART_REFERENCES} prior-art references "
            "per request."
        )


async def _fetch_documents_with_attempts(
    ids: list[str],
    *,
    providers: list[PatentDataAdapter] | None = None,
) -> tuple[list[PriorArtDocument], list[RetrievalAttempt]]:
    return await fetch_documents_from_providers(
        ids,
        providers or [PatentsViewAdapter(), GooglePatentsAdapter()],
    )
