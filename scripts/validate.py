from __future__ import annotations

import json
from pathlib import Path

from patent_copilot.core.chart_builder import build_claim_chart
from patent_copilot.core.schemas import MappingStatus, PriorArtDocument
from patent_copilot.tools.build_claim_chart import build_claim_chart_tool


def main() -> int:
    request = json.loads(Path("examples/build_claim_chart_request.json").read_text())
    documents = [PriorArtDocument.model_validate(item) for item in request["prior_art_texts"]]

    chart = build_claim_chart(request["claim_text"], documents)
    assert len(chart.rows) == 3
    assert chart.rows[1].mapping in {
        MappingStatus.DISCLOSED,
        MappingStatus.PARTIALLY_DISCLOSED,
    }
    assert chart.rows[1].evidence
    assert chart.markdown.startswith("| Element | Claim Element | Prior Art | Mapping | Evidence |")

    missing = build_claim_chart(
        "1. A device comprising: a quantum antenna configured to teleport packets.",
        [PriorArtDocument(id="US-DEMO-2", abstract="A hinge includes a pin and two leaves.")],
    )
    assert all(row.mapping != MappingStatus.DISCLOSED for row in missing.rows)

    # Importing and calling the async tool wrapper should work for manual text without API keys.
    import asyncio

    result = asyncio.run(
        build_claim_chart_tool(
            claim_text=request["claim_text"],
            prior_art_texts=request["prior_art_texts"],
        )
    )
    assert result["rows"][1]["evidence"][0]["prior_art_id"] == "US-DEMO-1"

    print("validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

