from patent_copilot import mcp_integration_cli


def test_review_summary_error_accepts_matching_summary() -> None:
    payload = {
        "rows": [
            {
                "mapping": "Disclosed",
                "confidence": "high",
                "review_flags": ["missing_terms"],
            },
            {
                "mapping": "Partially disclosed",
                "confidence": "medium",
                "review_flags": ["weak_section_support", "needs_practitioner_review"],
            },
        ],
        "review_summary": {
            "total_rows": 2,
            "rows_requiring_review": 2,
            "needs_practitioner_review": True,
            "mapping_counts": {"Disclosed": 1, "Partially disclosed": 1},
            "confidence_counts": {"high": 1, "medium": 1},
            "review_flag_counts": {
                "missing_terms": 1,
                "weak_section_support": 1,
                "needs_practitioner_review": 1,
            },
            "highest_risk_flags": [
                "weak_section_support",
                "missing_terms",
                "needs_practitioner_review",
            ],
        },
    }

    assert mcp_integration_cli._review_summary_error(payload) is None


def test_review_summary_error_rejects_mismatched_summary() -> None:
    payload = {
        "rows": [
            {
                "mapping": "Disclosed",
                "confidence": "high",
                "review_flags": ["missing_terms"],
            }
        ],
        "review_summary": {
            "total_rows": 1,
            "rows_requiring_review": 0,
            "needs_practitioner_review": False,
            "mapping_counts": {"Disclosed": 1},
            "confidence_counts": {"high": 1},
            "review_flag_counts": {},
            "highest_risk_flags": [],
        },
    }

    assert (
        mcp_integration_cli._review_summary_error(payload)
        == "review_summary rows_requiring_review does not match rows"
    )
