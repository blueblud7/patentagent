from __future__ import annotations

from patent_copilot.adapters.google_patents import GooglePatentsAdapter
from patent_copilot.adapters.patentsview import PatentsViewAdapter


async def search_prior_art_tool(
    query: str,
    jurisdiction: str = "US",
    date_before: str | None = None,
    limit: int = 10,
) -> dict:
    if jurisdiction.upper() != "US":
        raise ValueError("v0.1 currently implements live API search for US documents only.")

    try:
        adapter = PatentsViewAdapter()
        results = await adapter.search_prior_art(
            query,
            jurisdiction=jurisdiction,
            date_before=date_before,
            limit=limit,
        )
    except Exception:
        results = await GooglePatentsAdapter().search_prior_art(
            query,
            jurisdiction=jurisdiction,
            date_before=date_before,
            limit=limit,
        )
    return {"results": [item.model_dump(mode="json") for item in results]}
