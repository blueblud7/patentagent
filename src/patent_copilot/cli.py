from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from patent_copilot.core.chart_builder import build_claim_chart
from patent_copilot.core.schemas import PriorArtDocument


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline patent claim-chart demo.")
    parser.add_argument("request", help="Path to a build_claim_chart JSON request.")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Output format. Defaults to markdown.",
    )
    args = parser.parse_args(argv)

    payload = _read_json(Path(args.request))
    documents = [PriorArtDocument.model_validate(item) for item in payload.get("prior_art_texts", [])]
    if not documents:
        parser.error("request must include prior_art_texts for the offline demo")

    chart = build_claim_chart(payload["claim_text"], documents)
    if args.format == "json":
        json.dump(chart.model_dump(mode="json"), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(chart.markdown)
        sys.stdout.write("\n")
    return 0


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


if __name__ == "__main__":
    raise SystemExit(main())

