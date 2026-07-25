from __future__ import annotations

import argparse
import json
from pathlib import Path

from patent_copilot.core.chart_builder import build_claim_chart
from patent_copilot.core.evaluation import evaluate_claim_chart
from patent_copilot.core.schemas import PriorArtDocument


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate golden claim-chart fixtures.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a text table.")
    parser.add_argument(
        "--fixtures",
        default="examples/golden",
        help="Directory containing golden fixture JSON files.",
    )
    args = parser.parse_args()

    reports = []
    for fixture_path in sorted(Path(args.fixtures).glob("*.json")):
        fixture = json.loads(fixture_path.read_text())
        documents = [PriorArtDocument.model_validate(item) for item in fixture["prior_art_texts"]]
        chart = build_claim_chart(fixture["claim_text"], documents)
        reports.append(
            evaluate_claim_chart(
                chart,
                fixture["expected"],
                fixture_name=fixture.get("name", fixture_path.stem),
            )
        )

    if args.json:
        print(json.dumps([report.to_dict() for report in reports], indent=2))
    else:
        print("fixture,score,passed,issues")
        for report in reports:
            print(
                f"{report.fixture_name},{report.score:.3f},{str(report.passed).lower()},"
                f"{len(report.issues)}"
            )

    if not reports:
        return 1
    return 0 if all(report.passed for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())

