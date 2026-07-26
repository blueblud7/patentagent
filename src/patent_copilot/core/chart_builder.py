from __future__ import annotations

import csv
import io
from collections import defaultdict

from patent_copilot.core.claim_decomposer import decompose_claim
from patent_copilot.core.evidence_retriever import retrieve_evidence
from patent_copilot.core.patent_id import normalize_patent_id
from patent_copilot.core.schemas import (
    ChartReviewSummary,
    ClaimChart,
    ClaimChartRow,
    Confidence,
    DocumentCoverage,
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
        mapping, confidence = _mapping_for_evidence(best)
        gap = None
        if mapping == MappingStatus.NOT_FOUND:
            gap = "No supporting passage was found in the provided prior-art text."
        elif mapping == MappingStatus.PARTIALLY_DISCLOSED:
            gap = _partial_gap(best)

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
                review_flags=_review_flags(best, mapping),
                gap=gap,
            )
        )

    chart = ClaimChart(
        claim_text=claim_text,
        elements=elements,
        rows=rows,
        markdown="",
        csv="",
        review_summary=_review_summary(rows),
        document_coverage=_document_coverage(documents),
        warnings=_chart_warnings(documents),
    )
    chart.markdown = render_markdown(chart)
    chart.csv = render_csv(chart)
    return chart


def render_markdown(chart: ClaimChart) -> str:
    lines = [
        "| Element | Role | Claim Element | Best Prior Art | Mapping | Review Flags | Evidence | Analysis |",
        "|---|---|---|---|---|---|---|---|",
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
                    _escape(", ".join(row.review_flags) or "-"),
                    _escape(evidence_text),
                    _escape(row.analysis),
                ]
            )
            + " |"
        )

    if chart.review_summary:
        summary = chart.review_summary
        lines.extend(["", "## Review Summary", ""])
        lines.append(f"- Total rows: {summary.total_rows}")
        lines.append(f"- Rows requiring review: {summary.rows_requiring_review}")
        if summary.highest_risk_flags:
            lines.append(f"- Highest risk flags: {', '.join(summary.highest_risk_flags)}")
        lines.append(f"- Mapping counts: {_format_counts(summary.mapping_counts)}")

    if chart.document_coverage:
        lines.extend(["", "## Source Coverage", ""])
        for coverage in chart.document_coverage:
            warnings = f" Warnings: {'; '.join(coverage.warnings)}" if coverage.warnings else ""
            lines.append(
                "- "
                + _escape(coverage.id)
                + f" ({_escape(coverage.source)}): "
                + _escape(", ".join(coverage.sections) or "no searchable sections")
                + f"; {coverage.character_count} chars."
                + warnings
            )
    if chart.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in chart.warnings:
            lines.append(f"- {_escape(warning)}")
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
            "best_evidence_section",
            "best_evidence_locator",
            "best_evidence_quote",
            "matched_terms",
            "missing_terms",
            "term_coverage",
            "review_flags",
            "analysis",
            "gap",
        ]
    )
    for row in chart.rows:
        best_evidence = row.evidence[0] if row.evidence else None
        writer.writerow(
            [
                row.element_no,
                row.role.value,
                row.claim_element,
                row.prior_art_id or "",
                row.mapping.value,
                row.confidence.value,
                " | ".join(_format_evidence(item.section, item.locator, item.quote) for item in row.evidence),
                best_evidence.section if best_evidence else "",
                best_evidence.locator if best_evidence else "",
                best_evidence.quote if best_evidence else "",
                "; ".join(best_evidence.matched_terms) if best_evidence else "",
                "; ".join(best_evidence.missing_terms) if best_evidence else "",
                f"{best_evidence.term_coverage:.3f}" if best_evidence else "",
                "; ".join(row.review_flags),
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
        best = cited[0] if cited else None
        mapping, confidence = _mapping_for_evidence(best)
        gap = None
        if mapping == MappingStatus.NOT_FOUND:
            gap = "No supporting passage was found in this reference."
        elif mapping == MappingStatus.PARTIALLY_DISCLOSED:
            gap = _partial_gap(best, reference_scoped=True)
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
    return max(
        mappings,
        key=lambda item: item.evidence[0].score if item.evidence else 0.0,
    )


def _mapping_for_score(score: float) -> tuple[MappingStatus, Confidence]:
    if score >= 0.78:
        return MappingStatus.DISCLOSED, Confidence.HIGH
    if score >= 0.38:
        return MappingStatus.PARTIALLY_DISCLOSED, Confidence.MEDIUM
    if score > 0:
        return MappingStatus.AMBIGUOUS, Confidence.LOW
    return MappingStatus.NOT_FOUND, Confidence.LOW


def _mapping_for_evidence(evidence) -> tuple[MappingStatus, Confidence]:
    if evidence is None:
        return MappingStatus.NOT_FOUND, Confidence.LOW

    mapping, confidence = _mapping_for_score(evidence.score)
    section = evidence.section.lower()
    if mapping == MappingStatus.DISCLOSED and evidence.term_coverage < 0.8:
        return MappingStatus.PARTIALLY_DISCLOSED, Confidence.MEDIUM
    if mapping == MappingStatus.DISCLOSED and section not in {"claims", "description"}:
        if section == "abstract":
            return MappingStatus.PARTIALLY_DISCLOSED, Confidence.MEDIUM
        return MappingStatus.AMBIGUOUS, Confidence.LOW
    return mapping, confidence


def _partial_gap(evidence, *, reference_scoped: bool = False) -> str:
    if evidence and evidence.section.lower() not in {"claims", "description"}:
        return (
            "Only title/abstract support was found; claims or description text is needed "
            "before treating this as fully disclosed."
        )
    if evidence and evidence.missing_terms:
        terms = ", ".join(evidence.missing_terms[:8])
        return f"Potentially missing material terms from the cited passage: {terms}."
    if reference_scoped:
        return "This reference appears to cover only part of the limitation."
    return "Only partial textual support was found; practitioner review is required."


def _review_flags(evidence, mapping: MappingStatus) -> list[str]:
    flags: list[str] = []
    if mapping == MappingStatus.NOT_FOUND:
        flags.append("no_evidence")
    if evidence is None:
        return flags
    section = evidence.section.lower()
    if section not in {"claims", "description"}:
        flags.append("weak_section_support")
    if evidence.term_coverage < 0.8:
        flags.append("low_term_coverage")
    if evidence.missing_terms:
        flags.append("missing_terms")
    if mapping in {MappingStatus.PARTIALLY_DISCLOSED, MappingStatus.AMBIGUOUS}:
        flags.append("needs_practitioner_review")
    return flags


def _review_summary(rows: list[ClaimChartRow]) -> ChartReviewSummary:
    mapping_counts = _count_values(row.mapping.value for row in rows)
    confidence_counts = _count_values(row.confidence.value for row in rows)
    review_flag_counts = _count_values(flag for row in rows for flag in row.review_flags)
    rows_requiring_review = sum(1 for row in rows if row.review_flags)
    return ChartReviewSummary(
        total_rows=len(rows),
        rows_requiring_review=rows_requiring_review,
        needs_practitioner_review=rows_requiring_review > 0,
        mapping_counts=mapping_counts,
        confidence_counts=confidence_counts,
        review_flag_counts=review_flag_counts,
        highest_risk_flags=[
            flag
            for flag in (
                "no_evidence",
                "weak_section_support",
                "low_term_coverage",
                "missing_terms",
                "needs_practitioner_review",
            )
            if review_flag_counts.get(flag, 0) > 0
        ],
    )


def _count_values(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counts.items())


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


def _document_coverage(documents: list[PriorArtDocument]) -> list[DocumentCoverage]:
    coverage: list[DocumentCoverage] = []
    for document in documents:
        sections = document.searchable_sections()
        section_names = [name.lower() for name, _ in sections]
        warnings = _document_warnings(document, section_names)
        coverage.append(
            DocumentCoverage(
                id=document.id,
                title=document.title,
                url=document.url,
                source=str(document.metadata.get("source", "manual")),
                sections=section_names,
                character_count=sum(len(text) for _, text in sections),
                warnings=warnings,
            )
        )
    return coverage


def _chart_warnings(documents: list[PriorArtDocument]) -> list[str]:
    warnings: list[str] = []
    duplicate_groups = _duplicate_reference_groups(documents)
    if duplicate_groups:
        duplicate_details = [
            f"{normalized}: {', '.join(ids)}" for normalized, ids in duplicate_groups
        ]
        warnings.append(
            "Some references appear to be duplicates after patent ID normalization: "
            + "; ".join(duplicate_details)
            + "."
        )
    weak_documents = [
        document.id
        for document in documents
        if not document.claims and not document.description
    ]
    if weak_documents:
        warnings.append(
            "Some references lack claims/description text, so mappings may rely only on "
            f"title or abstract: {', '.join(weak_documents)}."
        )
    empty_documents = [document.id for document in documents if not document.searchable_sections()]
    if empty_documents:
        warnings.append(f"Some references have no searchable text: {', '.join(empty_documents)}.")
    return warnings


def _duplicate_reference_groups(documents: list[PriorArtDocument]) -> list[tuple[str, list[str]]]:
    ids_by_normalized: dict[str, list[str]] = defaultdict(list)
    for document in documents:
        ids_by_normalized[normalize_patent_id(document.id)].append(document.id)
    return [
        (normalized, ids)
        for normalized, ids in sorted(ids_by_normalized.items())
        if len(ids) > 1
    ]


def _document_warnings(document: PriorArtDocument, section_names: list[str]) -> list[str]:
    warnings: list[str] = []
    optional_errors = document.metadata.get("optional_endpoint_errors", [])
    if isinstance(optional_errors, list) and optional_errors:
        endpoints = [
            str(item.get("endpoint"))
            for item in optional_errors
            if isinstance(item, dict) and item.get("endpoint")
        ]
        warnings.append(f"optional endpoint failures: {', '.join(endpoints)}")
    if not section_names:
        warnings.append("no searchable text")
    if "claims" not in section_names:
        warnings.append("claims text missing")
    if "description" not in section_names:
        warnings.append("description text missing")
    if len(section_names) <= 2:
        warnings.append("limited source coverage")
    return warnings


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
