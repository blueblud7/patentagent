from patent_copilot.core.chart_builder import build_claim_chart
from patent_copilot.core.evaluation import evaluate_claim_chart
from patent_copilot.core.schemas import (
    ChartReviewSummary,
    ClaimChart,
    ClaimChartRow,
    Confidence,
    Evidence,
    MappingStatus,
    PriorArtDocument,
)


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
    assert report.metrics["review_summary_complete"] == 1.0


def test_evaluate_claim_chart_flags_weak_disclosure_quality() -> None:
    chart = ClaimChart(
        claim_text="1. A system comprising: a processor receiving encrypted sensor data.",
        elements=[],
        rows=[
            ClaimChartRow(
                element_no="1A",
                claim_element="a processor receiving encrypted sensor data",
                prior_art_id="US-DEMO",
                mapping=MappingStatus.DISCLOSED,
                analysis="Incorrectly marked as disclosed.",
                confidence=Confidence.HIGH,
                evidence=[
                    Evidence(
                        prior_art_id="US-DEMO",
                        section="Abstract",
                        quote="A processor receives sensor data.",
                        score=0.9,
                        why_relevant="Shares terms.",
                        matched_terms=["processor", "receive", "sensor", "data"],
                        missing_terms=["encrypted"],
                        term_coverage=0.75,
                    )
                ],
            )
        ],
        markdown="",
    )

    report = evaluate_claim_chart(chart, {"min_rows": 1}, fixture_name="weak")

    assert not report.passed
    assert report.metrics["review_summary_complete"] == 0.0
    assert report.metrics["no_weak_section_disclosure"] == 0.0
    assert report.metrics["no_weak_term_disclosure"] == 0.0
    assert {issue.code for issue in report.issues} == {
        "disclosed_from_weak_section",
        "disclosed_with_low_term_coverage",
        "missing_review_summary",
    }


def test_evaluate_claim_chart_flags_inconsistent_review_summary() -> None:
    chart = build_claim_chart(
        "1. A system comprising: a processor configured to receive sensor data.",
        [
            PriorArtDocument(
                id="US-DEMO",
                description="[0001] A processor receives sensor data from an interface.",
            )
        ],
    )
    chart.review_summary = ChartReviewSummary(
        total_rows=len(chart.rows),
        rows_requiring_review=0,
        needs_practitioner_review=False,
        mapping_counts={},
        confidence_counts={},
        review_flag_counts={},
        highest_risk_flags=[],
    )

    report = evaluate_claim_chart(chart, {"min_rows": 1}, fixture_name="bad_summary")

    assert not report.passed
    assert report.metrics["review_summary_complete"] == 0.0
    assert any(issue.code == "missing_review_summary" for issue in report.issues)
