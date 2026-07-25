from __future__ import annotations

from dataclasses import dataclass, field

from patent_copilot.core.schemas import ClaimChart, MappingStatus


@dataclass
class EvaluationIssue:
    severity: str
    code: str
    message: str
    element_no: str | None = None


@dataclass
class EvaluationReport:
    fixture_name: str
    score: float
    passed: bool
    metrics: dict[str, float]
    issues: list[EvaluationIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "fixture_name": self.fixture_name,
            "score": round(self.score, 4),
            "passed": self.passed,
            "metrics": {key: round(value, 4) for key, value in self.metrics.items()},
            "issues": [issue.__dict__ for issue in self.issues],
        }


def evaluate_claim_chart(chart: ClaimChart, expected: dict, *, fixture_name: str = "adhoc") -> EvaluationReport:
    issues: list[EvaluationIssue] = []
    rows = chart.rows
    expected_min_rows = int(expected.get("min_rows", 1))

    if len(rows) < expected_min_rows:
        issues.append(
            EvaluationIssue(
                severity="error",
                code="too_few_rows",
                message=f"Expected at least {expected_min_rows} rows, got {len(rows)}.",
            )
        )

    cited_rows = [row for row in rows if row.evidence]
    evidence_coverage = len(cited_rows) / max(len(rows), 1)

    unsupported_disclosures = [
        row for row in rows if row.mapping == MappingStatus.DISCLOSED and not row.evidence
    ]
    for row in unsupported_disclosures:
        issues.append(
            EvaluationIssue(
                severity="error",
                code="disclosed_without_evidence",
                message="A row marked Disclosed must include cited evidence.",
                element_no=row.element_no,
            )
        )

    not_found_rows = [row for row in rows if row.mapping == MappingStatus.NOT_FOUND]
    if not_found_rows:
        gap_coverage = len([row for row in not_found_rows if row.gap]) / len(not_found_rows)
    else:
        gap_coverage = 1.0

    must_disclose_terms = expected.get("must_disclose_terms", [])
    disclose_hits = 0
    for term in must_disclose_terms:
        matching = _rows_containing(rows, term)
        if matching and any(row.mapping != MappingStatus.NOT_FOUND and row.evidence for row in matching):
            disclose_hits += 1
        else:
            issues.append(
                EvaluationIssue(
                    severity="error",
                    code="missing_expected_disclosure",
                    message=f"Expected a supported mapping for term: {term}.",
                )
            )
    expected_disclosure_rate = disclose_hits / max(len(must_disclose_terms), 1)

    must_not_fully_disclose_terms = expected.get("must_not_fully_disclose_terms", [])
    gap_hits = 0
    for term in must_not_fully_disclose_terms:
        matching = _rows_containing(rows, term)
        if matching and all(row.mapping != MappingStatus.DISCLOSED for row in matching):
            gap_hits += 1
        else:
            issues.append(
                EvaluationIssue(
                    severity="error",
                    code="missed_expected_gap",
                    message=f"Expected this term not to be fully disclosed: {term}.",
                )
            )
    if must_not_fully_disclose_terms:
        expected_gap_rate = gap_hits / len(must_not_fully_disclose_terms)
    else:
        expected_gap_rate = 1.0

    reference_mapping_coverage = len([row for row in rows if row.reference_mappings]) / max(len(rows), 1)
    row_count_score = min(len(rows) / max(expected_min_rows, 1), 1.0)
    no_unsupported_disclosure = 1.0 if not unsupported_disclosures else 0.0

    metrics = {
        "row_count_score": row_count_score,
        "evidence_coverage": evidence_coverage,
        "reference_mapping_coverage": reference_mapping_coverage,
        "gap_coverage": gap_coverage,
        "expected_disclosure_rate": expected_disclosure_rate,
        "expected_gap_rate": expected_gap_rate,
        "no_unsupported_disclosure": no_unsupported_disclosure,
    }
    score = (
        0.15 * row_count_score
        + 0.2 * evidence_coverage
        + 0.15 * reference_mapping_coverage
        + 0.1 * gap_coverage
        + 0.2 * expected_disclosure_rate
        + 0.1 * expected_gap_rate
        + 0.1 * no_unsupported_disclosure
    )
    passed = score >= 0.85 and not any(issue.severity == "error" for issue in issues)
    return EvaluationReport(
        fixture_name=fixture_name,
        score=score,
        passed=passed,
        metrics=metrics,
        issues=issues,
    )


def _rows_containing(rows, term: str):
    term_lower = term.lower()
    return [row for row in rows if term_lower in row.claim_element.lower()]
