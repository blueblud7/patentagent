from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from patent_copilot.tools.build_claim_chart import build_claim_chart_tool
from patent_copilot.tools.search_prior_art import search_prior_art_tool


mcp = FastMCP("patent-copilot")


@mcp.tool()
async def search_prior_art(
    query: str,
    jurisdiction: str = "US",
    date_before: str | None = None,
    limit: int = 10,
) -> dict:
    """Search for prior-art candidates.

    v0.1 supports PatentsView-backed US search when PATENTSVIEW_API_KEY is set.
    """

    return await search_prior_art_tool(
        query=query,
        jurisdiction=jurisdiction,
        date_before=date_before,
        limit=limit,
    )


@mcp.tool()
async def build_claim_chart(
    claim_text: str,
    prior_art_ids: list[str] | None = None,
    prior_art_texts: list[dict] | None = None,
) -> dict:
    """Build an evidence-grounded claim chart for one claim.

    Provide prior_art_texts for local/keyless operation, or prior_art_ids with
    PATENTSVIEW_API_KEY configured for PatentsView lookup.
    """

    return await build_claim_chart_tool(
        claim_text=claim_text,
        prior_art_ids=prior_art_ids,
        prior_art_texts=prior_art_texts,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

