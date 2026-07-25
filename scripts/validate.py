from __future__ import annotations

import json
import asyncio
from pathlib import Path

from patent_copilot.core.chart_builder import build_claim_chart
from patent_copilot.core.evaluation import evaluate_claim_chart
from patent_copilot.core.mapping import PromptOnlyMappingModel
from patent_copilot.core.patent_id import google_patents_url, normalize_patent_id, patentsview_numeric_id
from patent_copilot.core.schemas import MappingStatus, PriorArtDocument
from patent_copilot.adapters.google_patents import parse_google_patents_html
from patent_copilot.tools.build_claim_chart import build_claim_chart_tool
from patent_copilot.tools.search_prior_art import search_prior_art_tool


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
    assert chart.markdown.startswith("| Element | Role | Claim Element | Best Prior Art | Mapping |")
    assert chart.csv.startswith("element_no,role,claim_element,best_prior_art_id,mapping")
    assert normalize_patent_id("us 12,345,678 b2") == "US12345678B2"
    assert normalize_patent_id("12345678") == "US12345678"
    assert patentsview_numeric_id("US12345678B2") == "12345678B2"
    assert google_patents_url("US12345678B2") == "https://patents.google.com/patent/US12345678B2/en"

    sample_html = Path("examples/google_patents_sample.html").read_text()
    parsed = parse_google_patents_html(sample_html, "US-DEMO-HTML")
    assert parsed.title == "Sensor classification system"
    assert "processor receives sensor data" in (parsed.description or "").lower()
    prompt_model = PromptOnlyMappingModel()
    prompt_result = asyncio.run(
        prompt_model.map_element(chart.elements[1], documents[0], chart.rows[1].evidence)
    )
    assert prompt_result.prior_art_id == "US-DEMO-1"
    assert "Claim element:" in prompt_result.prompt

    missing = build_claim_chart(
        "1. A device comprising: a quantum antenna configured to teleport packets.",
        [PriorArtDocument(id="US-DEMO-2", abstract="A hinge includes a pin and two leaves.")],
    )
    assert all(row.mapping != MappingStatus.DISCLOSED for row in missing.rows)
    assert any(row.gap for row in missing.rows)

    # Importing and calling the async tool wrapper should work for manual text without API keys.
    result = asyncio.run(
        build_claim_chart_tool(
            claim_text=request["claim_text"],
            prior_art_texts=request["prior_art_texts"],
        )
    )
    assert result["rows"][1]["evidence"][0]["prior_art_id"] == "US-DEMO-1"
    assert "csv" in result
    search_result = asyncio.run(search_prior_art_tool("sensor classifier", limit=1))
    assert search_result["results"]
    assert search_result["results"][0]["id"] == "manual-search-required"

    for fixture_path in sorted(Path("examples/golden").glob("*.json")):
        _validate_fixture(fixture_path)

    print("validation passed")
    return 0


def _validate_fixture(path: Path) -> None:
    fixture = json.loads(path.read_text())
    documents = [PriorArtDocument.model_validate(item) for item in fixture["prior_art_texts"]]
    chart = build_claim_chart(fixture["claim_text"], documents)
    expected = fixture["expected"]
    report = evaluate_claim_chart(chart, expected, fixture_name=fixture["name"])
    assert report.passed, report.to_dict()

    assert len(chart.rows) >= expected["min_rows"], fixture["name"]
    assert chart.markdown.count("\n") >= expected["min_rows"], fixture["name"]
    assert chart.csv.count("\n") >= expected["min_rows"], fixture["name"]
    assert all(row.reference_mappings for row in chart.rows), fixture["name"]

    for term in expected["must_disclose_terms"]:
        matching = [row for row in chart.rows if term.lower() in row.claim_element.lower()]
        assert matching, f"{fixture['name']}: no row for {term}"
        assert any(row.mapping != MappingStatus.NOT_FOUND for row in matching), fixture["name"]

    for term in expected["must_not_fully_disclose_terms"]:
        matching = [row for row in chart.rows if term.lower() in row.claim_element.lower()]
        assert matching, f"{fixture['name']}: no row for {term}"
        assert all(row.mapping != MappingStatus.DISCLOSED for row in matching), fixture["name"]


if __name__ == "__main__":
    raise SystemExit(main())
