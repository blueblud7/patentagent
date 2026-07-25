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
    assert processor_row.evidence[0].prior_art_id == "US-DEMO-1"
    assert "processor" in processor_row.evidence[0].quote.lower()
    assert "| Element | Claim Element | Prior Art | Mapping | Evidence | Analysis |" in chart.markdown


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

