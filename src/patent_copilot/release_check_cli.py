from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from patent_copilot.config import clean_env_value, env_has_value

COMMAND_TIMEOUT_SECONDS = 120
RELEASE_MANIFEST_SCHEMA_VERSION = "1.0"
RELEASE_MANIFEST_PATH = "dist/release_manifest.json"
DIST_CHECK_REPORT_PATH = "dist/distribution_check.json"
INSTALLED_WHEEL_SMOKE_REPORT_PATH = "dist/installed_wheel_smoke.json"
READINESS_REPORT_PATH = "dist/readiness_report.json"
LIVE_RETRIEVAL_REPORT_PATH = "dist/live_retrieval_smoke.json"

RELEASE_COMMANDS = [
    [sys.executable, "-m", "pytest"],
    [sys.executable, "-m", "ruff", "check", "."],
    [sys.executable, "scripts/ci_check.py"],
    [sys.executable, "-m", "build"],
    [sys.executable, "scripts/check_distribution.py", "--output", DIST_CHECK_REPORT_PATH],
    [
        sys.executable,
        "scripts/smoke_installed_wheel.py",
        "--output",
        INSTALLED_WHEEL_SMOKE_REPORT_PATH,
    ],
]
RELEASE_COMMAND_NAMES = [
    "unit_tests",
    "lint",
    "local_ci",
    "build_artifacts",
    "distribution_check",
    "installed_wheel_smoke",
]

LIVE_RETRIEVAL_COMMAND = [
    sys.executable,
    "scripts/smoke_live_retrieval.py",
    "--output",
    LIVE_RETRIEVAL_REPORT_PATH,
]
STRICT_LIVE_RETRIEVAL_COMMAND = [
    sys.executable,
    "scripts/smoke_live_retrieval.py",
    "--require-api-key",
    "--output",
    LIVE_RETRIEVAL_REPORT_PATH,
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the v0.1 local release gate.")
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Require live PatentsView retrieval to pass and score production_ready_v0.1.",
    )
    parser.add_argument(
        "--patent-id",
        help=(
            "Patent or publication ID to use for the live retrieval smoke. "
            "Defaults to PATENT_COPILOT_LIVE_PATENT_ID or US12000000B2."
        ),
    )
    args = parser.parse_args(argv)
    patent_id = clean_env_value(args.patent_id)
    if args.patent_id is not None and patent_id is None:
        parser.error("--patent-id must not be blank")
    has_live_key = env_has_value("PATENTSVIEW_API_KEY")

    if args.require_live and not has_live_key:
        print(
            "PATENTSVIEW_API_KEY is required when running "
            "`patent-copilot-release-check --require-live`."
        )
        _write_release_manifest(
            _release_manifest(
                success=False,
                require_live=args.require_live,
                api_key_configured=has_live_key,
                patent_id=patent_id,
                steps=[],
                failure_reason="PATENTSVIEW_API_KEY is required for strict live validation.",
            )
        )
        return 2

    steps = []
    for name, command in zip(RELEASE_COMMAND_NAMES, RELEASE_COMMANDS, strict=True):
        step = _run_step(name, command)
        steps.append(step)
        return_code = int(step["return_code"])
        if return_code != 0:
            _write_release_manifest(
                _release_manifest(
                    success=False,
                    require_live=args.require_live,
                    api_key_configured=has_live_key,
                    patent_id=patent_id,
                    steps=steps,
                )
            )
            return return_code

    live_command = _live_retrieval_command(
        require_live=args.require_live,
        patent_id=patent_id,
    )
    live_step = _run_step("live_retrieval_smoke", live_command)
    steps.append(live_step)
    live_return_code = int(live_step["return_code"])
    if live_return_code != 0:
        _write_release_manifest(
            _release_manifest(
                success=False,
                require_live=args.require_live,
                api_key_configured=has_live_key,
                patent_id=patent_id,
                steps=steps,
            )
        )
        return live_return_code

    readiness_command = [
        sys.executable,
        "scripts/readiness_audit.py",
        "--release-gate-passed",
        "--distribution-check-passed",
        "--installed-wheel-smoke-passed",
        "--output",
        READINESS_REPORT_PATH,
    ]
    if args.require_live or has_live_key:
        readiness_command.append("--live-retrieval-passed")
    _write_release_manifest(
        _release_manifest(
            success=True,
            require_live=args.require_live,
            api_key_configured=has_live_key,
            patent_id=patent_id,
            steps=steps,
        )
    )
    readiness_step = _run_step("readiness_audit", readiness_command)
    steps.append(readiness_step)
    return_code = int(readiness_step["return_code"])
    if return_code != 0:
        _write_release_manifest(
            _release_manifest(
                success=False,
                require_live=args.require_live,
                api_key_configured=has_live_key,
                patent_id=patent_id,
                steps=steps,
            )
        )
        return return_code

    _write_release_manifest(
        _release_manifest(
            success=True,
            require_live=args.require_live,
            api_key_configured=has_live_key,
            patent_id=patent_id,
            steps=steps,
        )
    )
    print("release checks passed")
    return 0


def _run(command: list[str]) -> int:
    print(f"+ {' '.join(command)}")
    try:
        completed = subprocess.run(command, check=False, timeout=COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        print(f"command timed out after {COMMAND_TIMEOUT_SECONDS}s: {' '.join(command)}")
        return 124
    return completed.returncode


def _run_step(name: str, command: list[str]) -> dict[str, object]:
    started = time.monotonic()
    return_code = _run(command)
    elapsed = time.monotonic() - started
    return _step_result(name, command, return_code, elapsed_seconds=elapsed)


def _step_result(
    name: str,
    command: list[str],
    return_code: int,
    *,
    elapsed_seconds: float,
) -> dict[str, object]:
    return {
        "name": name,
        "command": command,
        "return_code": return_code,
        "passed": return_code == 0,
        "elapsed_seconds": round(elapsed_seconds, 3),
    }


def _release_manifest(
    *,
    success: bool,
    require_live: bool,
    api_key_configured: bool,
    patent_id: str | None,
    steps: list[dict[str, object]],
    failure_reason: str | None = None,
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema_version": RELEASE_MANIFEST_SCHEMA_VERSION,
        "generated_at_epoch_seconds": round(time.time(), 3),
        "success": success,
        "require_live": require_live,
        "api_key_configured": api_key_configured,
        "patent_id": patent_id,
        "reports": {
            "distribution_check": DIST_CHECK_REPORT_PATH,
            "installed_wheel_smoke": INSTALLED_WHEEL_SMOKE_REPORT_PATH,
            "live_retrieval_smoke": LIVE_RETRIEVAL_REPORT_PATH,
            "readiness": READINESS_REPORT_PATH,
        },
        "steps": steps,
    }
    if failure_reason is not None:
        manifest["failure_reason"] = failure_reason
    return manifest


def _write_release_manifest(manifest: dict[str, object]) -> None:
    path = Path(RELEASE_MANIFEST_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(manifest, indent=2)}\n", encoding="utf-8")


def _live_retrieval_command(*, require_live: bool, patent_id: str | None = None) -> list[str]:
    command = list(STRICT_LIVE_RETRIEVAL_COMMAND if require_live else LIVE_RETRIEVAL_COMMAND)
    if patent_id is not None:
        command.extend(["--patent-id", patent_id])
    return command

if __name__ == "__main__":
    raise SystemExit(main())
