from __future__ import annotations

import csv
import io
from collections import defaultdict

from patent_copilot.core.claim_decomposer import decompose_claim
from patent_copilot.core.evidence_retriever import retrieve_evidence
from patent_copilot.core.schemas import (
    ClaimChart,
    ClaimChartRow,
    Confidence,
    MappingStatus,
    PriorArtDocument,
    ReferenceMapping,
)


def build_claim_chart(
    claim_text: str,
    documents: list[PriorArtDocument],
    *,
    evidence_per_reference: int = 2,
) -> ClaimChart:
    elements = decompose_claim(claim_text)
    rows: list[ClaimChartRow] = []

    for element in elements:
        evidence = retrieve_evidence(element, documents, limit=max(len(documents) * evidence_per_reference, 3))
        reference_mappings = _reference_mappings(evidence, documents, evidence_per_reference)
        best_mapping = _best_reference_mapping(reference_mappings)
        best = best_mapping.evidence[0] if best_mapping and best_mapping.evidence else None
        mapping = best_mapping.mapping if best_mapping else MappingStatus.NOT_FOUND
        confidence = best_mapping.confidence if best_mapping else Confidence.LOW

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
                role=element.role,
                evidence=evidence[:2],
                reference_mappings=reference_mappings,
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
        csv="",
    )
    chart.markdown = render_markdown(chart)
    chart.csv = render_csv(chart)
    return chart


def render_markdown(chart: ClaimChart) -> str:
    lines = [
        "| Element | Role | Claim Element | Best Prior Art | Mapping | Evidence | Analysis |",
        "|---|---|---|---|---|---|---|",
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
                    _escape(row.role.value),
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


def render_csv(chart: ClaimChart) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "element_no",
            "role",
            "claim_element",
            "best_prior_art_id",
            "mapping",
            "confidence",
            "evidence",
            "analysis",
            "gap",
        ]
    )
    for row in chart.rows:
        writer.writerow(
            [
                row.element_no,
                row.role.value,
                row.claim_element,
                row.prior_art_id or "",
                row.mapping.value,
                row.confidence.value,
                " | ".join(_format_evidence(item.section, item.locator, item.quote) for item in row.evidence),
                row.analysis,
                row.gap or "",
            ]
        )
    return output.getvalue()


def _reference_mappings(
    evidence: list,
    documents: list[PriorArtDocument],
    evidence_per_reference: int,
) -> list[ReferenceMapping]:
    by_reference: dict[str, list] = defaultdict(list)
    for item in evidence:
        by_reference[item.prior_art_id].append(item)

    mappings: list[ReferenceMapping] = []
    for document in documents:
        cited = by_reference.get(document.id, [])[:evidence_per_reference]
        best_score = cited[0].score if cited else 0.0
        mapping, confidence = _mapping_for_score(best_score)
        gap = None
        if mapping == MappingStatus.NOT_FOUND:
            gap = "No supporting passage was found in this reference."
        elif mapping == MappingStatus.PARTIALLY_DISCLOSED:
            gap = "This reference appears to cover only part of the limitation."
        mappings.append(
            ReferenceMapping(
                prior_art_id=document.id,
                mapping=mapping,
                confidence=confidence,
                evidence=cited,
                analysis=_analysis_for_reference(mapping),
                gap=gap,
            )
        )
    return mappings


def _best_reference_mapping(mappings: list[ReferenceMapping]) -> ReferenceMapping | None:
    if not mappings:
        return None
    return sorted(
        mappings,
        key=lambda item: item.evidence[0].score if item.evidence else 0.0,
        reverse=True,
    )[0]


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


def _analysis_for_reference(mapping: MappingStatus) -> str:
    if mapping == MappingStatus.DISCLOSED:
        return "This reference has strong text support for the limitation."
    if mapping == MappingStatus.PARTIALLY_DISCLOSED:
        return "This reference has partial text support and needs practitioner review."
    if mapping == MappingStatus.AMBIGUOUS:
        return "This reference uses related language, but correspondence is unclear."
    return "No cited passage supports this limitation in this reference."


def _format_evidence(section: str, locator: str | None, quote: str) -> str:
    prefix = section
    if locator:
        prefix = f"{prefix} [{locator}]"
    return f"{prefix}: {quote}"


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
