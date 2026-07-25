from patent_copilot.core.chart_builder import build_claim_chart
from patent_copilot.core.evaluation import evaluate_claim_chart
from patent_copilot.core.schemas import PriorArtDocument


def test_evaluate_claim_chart_scores_supported_fixture() -> None:
    chart = build_claim_chart(
        "1. A system comprising: a processor configured to receive sensor data.",
        [
            PriorArtDocument(
                id="US-DEMO",
                description="[0001] A processor receives sensor data from an interface.",
            )
        ],
    )

    report = evaluate_claim_chart(
        chart,
        {
            "min_rows": 2,
            "must_disclose_terms": ["processor"],
            "must_not_fully_disclose_terms": [],
        },
        fixture_name="unit",
    )

    assert report.passed
    assert report.metrics["no_unsupported_disclosure"] == 1.0

