import csv
import io

from patent_copilot.core.chart_builder import build_claim_chart
from patent_copilot.core.schemas import MappingStatus, PriorArtDocument


def test_build_claim_chart_cites_evidence_for_supported_elements() -> None:
    claim = (
        "1. A system comprising: a processor configured to receive sensor data; "
        "and a memory storing instructions to classify the sensor data."
    )
    docs = [
        PriorArtDocument(
            id="US-DEMO-1",
            title="Sensor classification system",
            abstract=(
                "A processor receives sensor measurements and classifies the measurements "
                "using stored instructions."
            ),
            description=(
                "[0042] The processor receives sensor data from an input interface. "
                "[0043] Memory stores instructions that classify the sensor data."
            ),
        )
    ]

    chart = build_claim_chart(claim, docs)

    assert len(chart.rows) == 3
    processor_row = chart.rows[1]
    assert processor_row.mapping in {
        MappingStatus.DISCLOSED,
        MappingStatus.PARTIALLY_DISCLOSED,
    }
    assert processor_row.evidence
    assert processor_row.reference_mappings
    assert processor_row.evidence[0].prior_art_id == "US-DEMO-1"
    assert "processor" in processor_row.evidence[0].quote.lower()
    assert "processor" in processor_row.evidence[0].matched_terms
    assert processor_row.evidence[0].term_coverage > 0
    assert chart.review_summary is not None
    assert chart.review_summary.total_rows == 3
    assert chart.review_summary.rows_requiring_review >= 1
    assert chart.review_summary.mapping_counts
    assert (
        "| Element | Role | Claim Element | Best Prior Art | Mapping | Review Flags | Evidence | Analysis |"
        in chart.markdown
    )
    assert "## Review Summary" in chart.markdown
    assert chart.csv.startswith("element_no,role,claim_element")


def test_csv_includes_audit_terms_for_best_evidence() -> None:
    claim = "1. A system comprising: a processor configured to receive sensor data."
    docs = [
        PriorArtDocument(
            id="US-DEMO-CSV",
            description="[0042] The processor receives sensor data from an input interface.",
        )
    ]

    chart = build_claim_chart(claim, docs)
    rows = list(csv.DictReader(io.StringIO(chart.csv)))

    assert rows
    supported = [row for row in rows if row["best_prior_art_id"] == "US-DEMO-CSV"]
    assert supported
    assert supported[0]["best_evidence_section"] == "Description"
    assert "processor" in supported[0]["matched_terms"]
    assert supported[0]["term_coverage"]
    assert "review_flags" in supported[0]


def test_build_claim_chart_does_not_disclose_without_evidence() -> None:
    claim = "1. A device comprising: a quantum antenna configured to teleport packets."
    docs = [
        PriorArtDocument(
            id="US-DEMO-2",
            title="Mechanical hinge",
            abstract="A hinge includes a pin and two leaves.",
        )
    ]

    chart = build_claim_chart(claim, docs)

    assert all(row.mapping != MappingStatus.DISCLOSED for row in chart.rows)
    assert any(row.mapping == MappingStatus.NOT_FOUND for row in chart.rows)


def test_build_claim_chart_reports_source_coverage_warnings() -> None:
    claim = "1. A device comprising: a battery configured to charge a phone."
    docs = [
        PriorArtDocument(
            id="US-DEMO-3",
            title="Battery charger",
            abstract="A battery charger supplies power to a portable phone.",
            metadata={"source": "patentsview"},
        )
    ]

    chart = build_claim_chart(claim, docs)
    payload = chart.model_dump(mode="json")

    assert payload["document_coverage"][0]["source"] == "patentsview"
    assert payload["document_coverage"][0]["sections"] == ["title", "abstract"]
    assert "claims text missing" in payload["document_coverage"][0]["warnings"]
    assert chart.warnings
    assert "Source Coverage" in chart.markdown


def test_build_claim_chart_reports_optional_endpoint_failures_in_coverage() -> None:
    claim = "1. A system comprising: a processor configured to receive sensor data."
    docs = [
        PriorArtDocument(
            id="US-DEMO-OPTIONAL",
            abstract="A processor receives sensor data.",
            metadata={
                "source": "patentsview",
                "optional_endpoint_errors": [
                    {
                        "endpoint": "/g_claim/",
                        "error": "PatentsView request failed for /g_claim/: HTTP 503.",
                    }
                ],
            },
        )
    ]

    chart = build_claim_chart(claim, docs)

    assert "optional endpoint failures: /g_claim/" in chart.document_coverage[0].warnings
    assert "optional endpoint failures: /g_claim/" in chart.markdown


def test_build_claim_chart_does_not_mark_abstract_only_evidence_as_fully_disclosed() -> None:
    claim = "1. A system comprising: a processor configured to receive sensor data."
    docs = [
        PriorArtDocument(
            id="US-DEMO-4",
            title="Processor receives sensor data",
            abstract="A processor configured to receive sensor data in a system.",
        )
    ]

    chart = build_claim_chart(claim, docs)
    supported_rows = [row for row in chart.rows if row.evidence]

    assert supported_rows
    assert all(row.mapping != MappingStatus.DISCLOSED for row in supported_rows)
    assert any("claims or description text is needed" in (row.gap or "") for row in supported_rows)
    assert any("weak_section_support" in row.review_flags for row in supported_rows)
    assert "weak_section_support" in chart.csv
    assert "weak_section_support" in chart.markdown


def test_build_claim_chart_reports_missing_terms_for_partial_mapping() -> None:
    claim = (
        "1. A system comprising: a processor configured to receive encrypted sensor data "
        "from a wireless gateway."
    )
    docs = [
        PriorArtDocument(
            id="US-DEMO-5",
            description="[0042] The processor receives sensor data from an interface.",
        )
    ]

    chart = build_claim_chart(claim, docs)
    supported_rows = [row for row in chart.rows if row.evidence]

    assert supported_rows
    assert any(row.evidence[0].missing_terms for row in supported_rows)
    assert any("Potentially missing material terms" in (row.gap or "") for row in supported_rows)
    assert any("missing_terms" in row.review_flags for row in supported_rows)


def test_build_claim_chart_marks_not_found_rows_for_review() -> None:
    claim = "1. A device comprising: a quantum antenna configured to teleport packets."
    docs = [
        PriorArtDocument(
            id="US-DEMO-NOT-FOUND",
            title="Mechanical hinge",
            abstract="A hinge includes a pin and two leaves.",
        )
    ]

    chart = build_claim_chart(claim, docs)
    not_found_rows = [row for row in chart.rows if row.mapping == MappingStatus.NOT_FOUND]

    assert not_found_rows
    assert all(row.review_flags == ["no_evidence"] for row in not_found_rows)
    payload = chart.model_dump(mode="json")
    assert any("no_evidence" in row["review_flags"] for row in payload["rows"])
    assert payload["review_summary"]["review_flag_counts"]["no_evidence"] == len(not_found_rows)
    assert payload["review_summary"]["needs_practitioner_review"] is True
    assert "no_evidence" in payload["review_summary"]["highest_risk_flags"]


def test_build_claim_chart_summarizes_review_flags() -> None:
    claim = (
        "1. A system comprising: a processor configured to receive encrypted sensor data "
        "from a wireless gateway."
    )
    docs = [
        PriorArtDocument(
            id="US-DEMO-SUMMARY",
            abstract="A processor receives sensor data.",
        )
    ]

    chart = build_claim_chart(claim, docs)

    assert chart.review_summary is not None
    assert chart.review_summary.total_rows == len(chart.rows)
    assert chart.review_summary.rows_requiring_review == sum(
        1 for row in chart.rows if row.review_flags
    )
    assert chart.review_summary.review_flag_counts["weak_section_support"] >= 1
    assert chart.review_summary.review_flag_counts["missing_terms"] >= 1
    assert chart.review_summary.highest_risk_flags[:3] == [
        "no_evidence",
        "weak_section_support",
        "low_term_coverage",
    ]
    assert "Highest risk flags:" in chart.markdown


def test_build_claim_chart_warns_about_normalized_duplicate_reference_ids() -> None:
    claim = "1. A device comprising: a processor configured to receive sensor data."
    docs = [
        PriorArtDocument(
            id="US 12,000,000 B2",
            description="A processor receives sensor data from a device interface.",
        ),
        PriorArtDocument(
            id="US12000000B2",
            description="A processor receives sensor data from a device interface.",
        ),
    ]

    chart = build_claim_chart(claim, docs)

    assert any("duplicates after patent ID normalization" in warning for warning in chart.warnings)
    assert "US12000000B2" in chart.markdown
    assert "duplicates after patent ID normalization" in chart.markdown
