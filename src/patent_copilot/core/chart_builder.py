from __future__ import annotations

from patent_copilot.core.claim_decomposer import decompose_claim
from patent_copilot.core.evidence_retriever import retrieve_evidence
from patent_copilot.core.schemas import (
    ClaimChart,
    ClaimChartRow,
    Confidence,
    MappingStatus,
    PriorArtDocument,
)


def build_claim_chart(claim_text: str, documents: list[PriorArtDocument]) -> ClaimChart:
    elements = decompose_claim(claim_text)
    rows: list[ClaimChartRow] = []

    for element in elements:
        evidence = retrieve_evidence(element, documents)
        best = evidence[0] if evidence else None
        mapping, confidence = _mapping_for_score(best.score if best else 0.0)
        gap = None
        if mapping == MappingStatus.NOT_FOUND:
            gap = "No supporting passage was found in the provided prior-art text."
        elif mapping == MappingStatus.PARTIALLY_DISCLOSED:
            gap = "Only partial textual support was found; practitioner review is required."

        rows.append(
            ClaimChartRow(
                element_no=element.element_no,
                claim_element=element.text,
                prior_art_id=best.prior_art_id if best else None,
                mapping=mapping,
                evidence=evidence[:2],
                analysis=_analysis(element.text, mapping),
                confidence=confidence,
                gap=gap,
            )
        )

    chart = ClaimChart(
        claim_text=claim_text,
        elements=elements,
        rows=rows,
        markdown="",
    )
    chart.markdown = render_markdown(chart)
    return chart


def render_markdown(chart: ClaimChart) -> str:
    lines = [
        "| Element | Claim Element | Prior Art | Mapping | Evidence | Analysis |",
        "|---|---|---|---|---|---|",
    ]
    for row in chart.rows:
        evidence_text = "<br>".join(
            _format_evidence(evidence.section, evidence.locator, evidence.quote)
            for evidence in row.evidence
        )
        if not evidence_text:
            evidence_text = row.gap or "No cited evidence."
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape(row.element_no),
                    _escape(row.claim_element),
                    _escape(row.prior_art_id or "-"),
                    _escape(row.mapping.value),
                    _escape(evidence_text),
                    _escape(row.analysis),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _mapping_for_score(score: float) -> tuple[MappingStatus, Confidence]:
    if score >= 0.78:
        return MappingStatus.DISCLOSED, Confidence.HIGH
    if score >= 0.38:
        return MappingStatus.PARTIALLY_DISCLOSED, Confidence.MEDIUM
    if score > 0:
        return MappingStatus.AMBIGUOUS, Confidence.LOW
    return MappingStatus.NOT_FOUND, Confidence.LOW


def _analysis(element_text: str, mapping: MappingStatus) -> str:
    if mapping == MappingStatus.DISCLOSED:
        return "The cited passage appears to disclose this claim element."
    if mapping == MappingStatus.PARTIALLY_DISCLOSED:
        return "The cited passage overlaps with this element but may not cover every limitation."
    if mapping == MappingStatus.AMBIGUOUS:
        return "Some related language was found, but the technical correspondence is unclear."
    return "No evidence-backed mapping is made for this element."


def _format_evidence(section: str, locator: str | None, quote: str) -> str:
    prefix = section
    if locator:
        prefix = f"{prefix} [{locator}]"
    return f"{prefix}: {quote}"


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")

