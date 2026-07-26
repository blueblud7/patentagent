from __future__ import annotations

import argparse

from patent_copilot.config import clean_env_value, env_has_value
from patent_copilot.release_check_cli import _release_manifest, _write_release_manifest

CI_RELEASE_STEPS = [
    ("unit_tests", ["pytest"]),
    ("lint", ["ruff", "check", "."]),
    ("validation", ["python", "scripts/validate.py"]),
    ("golden_eval", ["patent-copilot-eval", "--json"]),
    ("preflight", ["patent-copilot-preflight"]),
    ("mcp_smoke", ["patent-copilot-smoke"]),
    ("mcp_integration", ["patent-copilot-mcp-integration"]),
    ("build_artifacts", ["python", "-m", "build"]),
    (
        "distribution_check",
        ["python", "scripts/check_distribution.py", "--output", "dist/distribution_check.json"],
    ),
    (
        "installed_wheel_smoke",
        ["patent-copilot-installed-wheel-smoke", "--output", "dist/installed_wheel_smoke.json"],
    ),
    (
        "live_retrieval_smoke",
        ["patent-copilot-live-retrieval-smoke", "--output", "dist/live_retrieval_smoke.json"],
    ),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a release manifest for completed CI steps.")
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Record that strict live retrieval was required for this manifest.",
    )
    parser.add_argument(
        "--patent-id",
        help="Optional live retrieval patent or publication ID used for the CI run.",
    )
    args = parser.parse_args(argv)
    patent_id = clean_env_value(args.patent_id)
    if args.patent_id is not None and patent_id is None:
        parser.error("--patent-id must not be blank")

    steps = [
        {
            "name": name,
            "command": command,
            "return_code": 0,
            "passed": True,
            "elapsed_seconds": 0.0,
        }
        for name, command in CI_RELEASE_STEPS
    ]
    if args.require_live:
        steps.append(
            {
                "name": "strict_live_retrieval_smoke",
                "command": [
                    "patent-copilot-live-retrieval-smoke",
                    "--require-api-key",
                    "--output",
                    "dist/live_retrieval_smoke.json",
                ],
                "return_code": 0,
                "passed": True,
                "elapsed_seconds": 0.0,
            }
        )

    _write_release_manifest(
        _release_manifest(
            success=True,
            require_live=args.require_live,
            api_key_configured=env_has_value("PATENTSVIEW_API_KEY"),
            patent_id=patent_id,
            steps=steps,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
