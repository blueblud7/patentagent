from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from patent_copilot.contracts import MAX_PRIOR_ART_REFERENCES
from patent_copilot.tools.build_claim_chart import build_claim_chart_mcp_response
from patent_copilot.tools.search_prior_art import search_prior_art_mcp_response

mcp = FastMCP("patent-copilot")


NonEmptyString = Annotated[str, Field(min_length=1)]
DateBefore = Annotated[str | None, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
SearchLimit = Annotated[int, Field(ge=1, le=100)]


class PriorArtTextInput(BaseModel):
    id: NonEmptyString
    title: str | None = None
    abstract: str | None = None
    claims: str | None = None
    description: str | None = None
    url: str | None = None


PriorArtIds = Annotated[list[NonEmptyString] | None, Field(max_length=MAX_PRIOR_ART_REFERENCES)]
PriorArtTexts = Annotated[list[PriorArtTextInput] | None, Field(max_length=MAX_PRIOR_ART_REFERENCES)]


@mcp.tool()
async def search_prior_art(
    query: NonEmptyString,
    jurisdiction: Literal["US"] = "US",
    date_before: DateBefore = None,
    limit: SearchLimit = 10,
) -> dict:
    """Search for prior-art candidates.

    v0.1 supports PatentsView-backed US search when PATENTSVIEW_API_KEY is set.
    """

    return await search_prior_art_mcp_response(
        query=query,
        jurisdiction=jurisdiction,
        date_before=date_before,
        limit=limit,
    )


@mcp.tool()
async def build_claim_chart(
    claim_text: NonEmptyString,
    prior_art_ids: PriorArtIds = None,
    prior_art_texts: PriorArtTexts = None,
) -> dict:
    """Build an evidence-grounded claim chart for one claim.

    Provide prior_art_texts for local/keyless operation, or prior_art_ids with
    PATENTSVIEW_API_KEY configured for PatentsView lookup.
    """

    return await build_claim_chart_mcp_response(
        claim_text=claim_text,
        prior_art_ids=prior_art_ids,
        prior_art_texts=_prior_art_texts_payload(prior_art_texts),
    )


def _prior_art_texts_payload(
    prior_art_texts: list[PriorArtTextInput] | None,
) -> list[dict] | None:
    if prior_art_texts is None:
        return None
    return [item.model_dump(exclude_none=True) for item in prior_art_texts]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
