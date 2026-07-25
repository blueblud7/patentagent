from __future__ import annotations

from patent_copilot.adapters.patentsview import PatentsViewAdapter
from patent_copilot.core.chart_builder import build_claim_chart as build_chart
from patent_copilot.core.schemas import ClaimChart, PriorArtDocument


async def build_claim_chart_tool(
    claim_text: str,
    prior_art_ids: list[str] | None = None,
    prior_art_texts: list[dict] | None = None,
) -> dict:
    documents = [PriorArtDocument.model_validate(item) for item in prior_art_texts or []]

    missing_ids = [item for item in prior_art_ids or [] if item not in {doc.id for doc in documents}]
    if missing_ids:
        fetched = await PatentsViewAdapter().fetch_documents(missing_ids)
        documents.extend(fetched)

    if not documents:
        raise ValueError(
            "No prior-art documents available. Provide prior_art_texts or configure PATENTSVIEW_API_KEY."
        )

    chart: ClaimChart = build_chart(claim_text, documents)
    return chart.model_dump(mode="json")

