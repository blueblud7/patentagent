from __future__ import annotations

import argparse
import json
import sys
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from patent_copilot.contracts import MAX_PRIOR_ART_REFERENCES
from patent_copilot.core.chart_builder import build_claim_chart
from patent_copilot.core.schemas import PriorArtDocument

_TEXT_FIELDS = ("title", "abstract", "claims", "description")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline patent claim-chart demo.")
    parser.add_argument("request", help="Path to a build_claim_chart JSON request.")
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "csv", "summary"),
        default="markdown",
        help="Output format. Defaults to markdown.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the formatted output instead of stdout.",
    )
    args = parser.parse_args(argv)

    try:
        payload = _read_json(Path(args.request))
    except OSError as exc:
        parser.error(f"could not read request file: {exc}")
    except JSONDecodeError as exc:
        parser.error(f"request must be valid JSON: {exc}")
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))

    claim_text = payload.get("claim_text")
    if not isinstance(claim_text, str) or not claim_text.strip():
        parser.error("request must include non-empty claim_text")
    try:
        documents = _validate_prior_art_texts(payload.get("prior_art_texts", []))
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    if not documents:
        _reject_id_only_offline_request(parser, payload.get("prior_art_ids"))
        parser.error("request must include prior_art_texts for the offline demo")

    chart = build_claim_chart(claim_text, documents)
    output = _format_chart_output(chart, args.format)
    if args.output is not None:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        except OSError as exc:
            parser.error(f"could not write output file: {exc}")
        sys.stderr.write(f"wrote {args.output}\n")
        return 0

    sys.stdout.write(output)
    return 0


def _format_chart_output(chart, output_format: str) -> str:
    if output_format == "json":
        return f"{json.dumps(chart.model_dump(mode='json'), indent=2, ensure_ascii=False)}\n"
    if output_format == "summary":
        payload = {
            "claim_text": chart.claim_text,
            "review_summary": chart.review_summary.model_dump(mode="json")
            if chart.review_summary
            else None,
            "warnings": chart.warnings,
            "document_coverage": [
                item.model_dump(mode="json") for item in chart.document_coverage
            ],
        }
        return f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n"
    if output_format == "csv":
        return chart.csv
    return f"{chart.markdown}\n"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise TypeError("request JSON must be an object")
    return payload


def _validate_prior_art_texts(value: Any) -> list[PriorArtDocument]:
    if not isinstance(value, list):
        raise TypeError("prior_art_texts must be a list of document objects")
    if len(value) > MAX_PRIOR_ART_REFERENCES:
        raise ValueError(
            f"offline demo accepts at most {MAX_PRIOR_ART_REFERENCES} prior-art references"
        )

    documents: list[PriorArtDocument] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise TypeError(f"prior_art_texts[{index}] must be an object")
        if not isinstance(item.get("id"), str) or not item["id"].strip():
            raise ValueError(f"prior_art_texts[{index}].id must be a non-empty string")
        if not any(isinstance(item.get(field), str) and item[field].strip() for field in _TEXT_FIELDS):
            raise ValueError(
                f"prior_art_texts[{index}] must include at least one text field: "
                f"{', '.join(_TEXT_FIELDS)}"
            )
        documents.append(PriorArtDocument.model_validate(item))
    return documents


def _reject_id_only_offline_request(parser: argparse.ArgumentParser, value: Any) -> None:
    if not isinstance(value, list) or not value:
        return
    parser.error(
        "offline demo does not fetch prior_art_ids. Provide prior_art_texts, "
        "or use the MCP build_claim_chart tool with network retrieval configured."
    )


if __name__ == "__main__":
    raise SystemExit(main())
