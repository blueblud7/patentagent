from __future__ import annotations

from patent_copilot.adapters.google_patents import GooglePatentsAdapter
from patent_copilot.adapters.patentsview import PatentsViewAdapter
from patent_copilot.core.chart_builder import build_claim_chart as build_chart
from patent_copilot.core.patent_id import normalize_patent_id
from patent_copilot.core.schemas import ClaimChart, PriorArtDocument


async def build_claim_chart_tool(
    claim_text: str,
    prior_art_ids: list[str] | None = None,
    prior_art_texts: list[dict] | None = None,
) -> dict:
    documents = [PriorArtDocument.model_validate(item) for item in prior_art_texts or []]

    known_ids = {normalize_patent_id(doc.id) for doc in documents}
    missing_ids = []
    for item in prior_art_ids or []:
        normalized = normalize_patent_id(item)
        if normalized not in known_ids:
            missing_ids.append(normalized)
    if missing_ids:
        fetched = await _fetch_documents_with_fallback(missing_ids)
        documents.extend(fetched)

    if not documents:
        raise ValueError(
            "No prior-art documents available. Provide prior_art_texts or configure PATENTSVIEW_API_KEY."
        )

    chart: ClaimChart = build_chart(claim_text, documents)
    return chart.model_dump(mode="json")


async def _fetch_documents_with_fallback(ids: list[str]) -> list[PriorArtDocument]:
    try:
        return await PatentsViewAdapter().fetch_documents(ids)
    except Exception:
        return await GooglePatentsAdapter().fetch_documents(ids)
