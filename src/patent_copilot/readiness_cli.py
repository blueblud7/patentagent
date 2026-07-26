from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patent_copilot import __version__

MIN_RUNTIME = (3, 11)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
READINESS_REPORT_SCHEMA_VERSION = "1.12"
DEFAULT_EVIDENCE_ARTIFACTS = {
    "distribution_check": "dist/distribution_check.json",
    "installed_wheel_smoke": "dist/installed_wheel_smoke.json",
    "live_retrieval_smoke": "dist/live_retrieval_smoke.json",
    "release_manifest": "dist/release_manifest.json",
}
EVIDENCE_ARTIFACT_REQUIRED_KEYS = {
    "distribution_check": {"message", "artifacts", "required_modules_present", "env_example_valid"},
    "installed_wheel_smoke": {
        "message",
        "installed",
        "console_scripts_checked",
        "offline_demo_ran",
        "summary_demo_ran",
    },
    "live_retrieval_smoke": {"message", "provider", "api_key_configured", "skipped"},
    "release_manifest": {"schema_version", "success", "reports", "steps"},
}
REQUIRED_RELEASE_MANIFEST_STEPS = {
    "unit_tests",
    "lint",
    "build_artifacts",
    "distribution_check",
    "installed_wheel_smoke",
    "live_retrieval_smoke",
}


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    points: int
    passed: bool
    required: bool
    detail: str

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "points": self.points,
            "passed": self.passed,
            "required": self.required,
            "detail": self.detail,
        }


def build_readiness_report(
    *,
    release_gate_passed: bool = False,
    distribution_check_passed: bool = False,
    installed_wheel_smoke_passed: bool = False,
    live_retrieval_passed: bool = False,
    generated_at: str | None = None,
    evidence_artifacts: dict[str, str] | None = None,
) -> dict[str, Any]:
    artifact_paths = evidence_artifacts or dict(DEFAULT_EVIDENCE_ARTIFACTS)
    artifact_status = _evidence_artifact_status(artifact_paths)
    artifact_errors = _evidence_artifact_errors(artifact_status)
    flag_errors = _evidence_flag_errors(
        artifact_status,
        distribution_check_passed=distribution_check_passed,
        installed_wheel_smoke_passed=installed_wheel_smoke_passed,
        live_retrieval_passed=live_retrieval_passed,
    )
    checks = _checks(
        release_gate_passed=release_gate_passed,
        distribution_check_passed=distribution_check_passed,
        installed_wheel_smoke_passed=installed_wheel_smoke_passed,
        live_retrieval_passed=live_retrieval_passed,
        evidence_artifact_status=artifact_status,
    )
    score = sum(check.points for check in checks if check.passed)
    max_score = sum(check.points for check in checks)
    blockers = [check.detail for check in checks if check.required and not check.passed]
    gaps = [check.detail for check in checks if not check.required and not check.passed]

    return {
        "schema_version": READINESS_REPORT_SCHEMA_VERSION,
        "package_version": __version__,
        "generated_at": generated_at or _utc_now_iso(),
        "evidence": {
            "release_gate_passed": release_gate_passed,
            "distribution_check_passed": distribution_check_passed,
            "installed_wheel_smoke_passed": installed_wheel_smoke_passed,
            "live_retrieval_passed": live_retrieval_passed,
        },
        "evidence_artifacts": artifact_paths,
        "evidence_artifact_status": artifact_status,
        "evidence_artifact_errors": artifact_errors,
        "evidence_flag_errors": flag_errors,
        "score": score,
        "max_score": max_score,
        "percent": round(score / max_score, 3),
        "grade": _grade(score),
        "ship_decision": _ship_decision(blockers, gaps),
        "summary": _summary(blockers, gaps),
        "next_commands": _next_commands(blockers, gaps),
        "blockers": blockers,
        "gaps": gaps,
        "checks": [check.model_dump() for check in checks],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report v0.1 production-readiness score.")
    parser.add_argument(
        "--release-gate-passed",
        action="store_true",
        help="Include points for a just-completed release_check.py run.",
    )
    parser.add_argument(
        "--distribution-check-passed",
        action="store_true",
        help="Include points for a just-completed distribution artifact check.",
    )
    parser.add_argument(
        "--installed-wheel-smoke-passed",
        action="store_true",
        help="Include points for a just-completed installed wheel offline smoke.",
    )
    parser.add_argument(
        "--live-retrieval-passed",
        action="store_true",
        help="Include points for a just-completed live PatentsView retrieval smoke.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the readiness report JSON.",
    )
    args = parser.parse_args(argv)
    report = build_readiness_report(
        release_gate_passed=args.release_gate_passed,
        distribution_check_passed=args.distribution_check_passed,
        installed_wheel_smoke_passed=args.installed_wheel_smoke_passed,
        live_retrieval_passed=args.live_retrieval_passed,
    )
    report_json = json.dumps(report, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{report_json}\n", encoding="utf-8")
    print(report_json)
    return 0 if not report["blockers"] else 2


def _checks(
    *,
    release_gate_passed: bool,
    distribution_check_passed: bool,
    installed_wheel_smoke_passed: bool,
    live_retrieval_passed: bool,
    evidence_artifact_status: dict[str, dict[str, Any]],
) -> list[ReadinessCheck]:
    dist_path = PROJECT_ROOT / "dist"
    evidence_artifacts_valid = _evidence_artifacts_valid(evidence_artifact_status)
    evidence_flags_match_artifacts = _evidence_flags_match_artifacts(
        evidence_artifact_status,
        distribution_check_passed=distribution_check_passed,
        installed_wheel_smoke_passed=installed_wheel_smoke_passed,
        live_retrieval_passed=live_retrieval_passed,
    )
    return [
        ReadinessCheck(
            name="python_runtime",
            points=10,
            passed=sys.version_info >= MIN_RUNTIME,
            required=True,
            detail="Python runtime must be >=3.11.",
        ),
        ReadinessCheck(
            name="mcp_runtime_dependency",
            points=10,
            passed=(
                importlib.util.find_spec("mcp") is not None
                and importlib.util.find_spec("pydantic") is not None
            ),
            required=True,
            detail="MCP runtime dependencies must be installed: mcp and pydantic.",
        ),
        ReadinessCheck(
            name="http_client_dependency",
            points=5,
            passed=importlib.util.find_spec("httpx") is not None,
            required=True,
            detail="httpx must be installed for live patent retrieval.",
        ),
        ReadinessCheck(
            name="release_gate",
            points=20,
            passed=release_gate_passed,
            required=True,
            detail="Release gate must pass: tests, lint, local CI, build, and smoke checks.",
        ),
        ReadinessCheck(
            name="golden_fixture_depth",
            points=10,
            passed=len(list((PROJECT_ROOT / "examples" / "golden").glob("*.json"))) >= 6,
            required=True,
            detail="At least six golden fixtures should protect deterministic mapping quality.",
        ),
        ReadinessCheck(
            name="mcp_contract_documented",
            points=10,
            passed=_readme_contains("## MCP Response Contracts", "`ok` flag"),
            required=True,
            detail="MCP response contracts must be documented for client integration.",
        ),
        ReadinessCheck(
            name="build_artifacts_present",
            points=10,
            passed=dist_path.exists() and any(dist_path.glob("*.whl")),
            required=True,
            detail="Built wheel artifact must be present after release build.",
        ),
        ReadinessCheck(
            name="distribution_check",
            points=5,
            passed=distribution_check_passed,
            required=True,
            detail=(
                "Distribution artifact check must pass, including wheel modules, "
                "entry point targets, callables, wheel metadata, and sdist contents."
            ),
        ),
        ReadinessCheck(
            name="installed_wheel_smoke",
            points=5,
            passed=installed_wheel_smoke_passed,
            required=True,
            detail=(
                "Installed wheel smoke must pass by installing the built wheel into a temporary "
                "environment and running the offline demo."
            ),
        ),
        ReadinessCheck(
            name="evidence_artifact_integrity",
            points=0,
            passed=evidence_artifacts_valid,
            required=True,
            detail=(
                "Release evidence artifacts must exist, be valid JSON, and include "
                "their expected top-level keys."
            ),
        ),
        ReadinessCheck(
            name="evidence_flag_consistency",
            points=0,
            passed=evidence_flags_match_artifacts,
            required=True,
            detail=(
                "Readiness evidence flags must match the parsed release artifact "
                "results they claim to represent."
            ),
        ),
        ReadinessCheck(
            name="live_patentsview_retrieval",
            points=10,
            passed=live_retrieval_passed,
            required=False,
            detail=(
                "Live PatentsView retrieval smoke has not passed in this environment; "
                "configure PATENTSVIEW_API_KEY and run the live smoke."
            ),
        ),
        ReadinessCheck(
            name="legal_disclaimer_documented",
            points=5,
            passed=_readme_contains("## Legal Notice", "not legal advice"),
            required=True,
            detail="Legal notice must remain documented.",
        ),
    ]


def _readme_contains(*needles: str) -> bool:
    readme_path = PROJECT_ROOT / "README.md"
    if not readme_path.exists():
        return False
    content = readme_path.read_text(encoding="utf-8")
    return all(needle in content for needle in needles)


def _evidence_artifact_status(artifacts: dict[str, str]) -> dict[str, dict[str, Any]]:
    status = {}
    for name, artifact_path in artifacts.items():
        path = PROJECT_ROOT / artifact_path
        exists = path.exists()
        json_valid = False
        json_error = None
        parsed_json = None
        if exists:
            try:
                parsed_json = json.loads(path.read_text(encoding="utf-8"))
                json_valid = True
            except (OSError, json.JSONDecodeError) as exc:
                json_error = str(exc)
        required_keys = EVIDENCE_ARTIFACT_REQUIRED_KEYS.get(name, set())
        missing_keys = _missing_json_keys(parsed_json, required_keys)
        result_state, result_errors = _artifact_result(name, parsed_json)
        status[name] = {
            "path": artifact_path,
            "exists": exists,
            "size_bytes": path.stat().st_size if exists else 0,
            "json_valid": json_valid,
            "json_error": json_error,
            "json_required_keys": sorted(required_keys),
            "json_required_keys_present": json_valid and not missing_keys,
            "missing_json_keys": missing_keys,
            "result_state": result_state,
            "result_errors": result_errors,
            "result_consistent": not result_errors,
        }
    return status


def _missing_json_keys(value: Any, required_keys: set[str]) -> list[str]:
    if not required_keys:
        return []
    if not isinstance(value, dict):
        return sorted(required_keys)
    return sorted(key for key in required_keys if key not in value)


def _evidence_artifacts_valid(status: dict[str, dict[str, Any]]) -> bool:
    expected_names = set(DEFAULT_EVIDENCE_ARTIFACTS)
    if set(status) != expected_names:
        return False
    return all(
        item["exists"]
        and item["json_valid"]
        and item["json_required_keys_present"]
        and item["result_consistent"]
        for item in status.values()
    )


def _evidence_flags_match_artifacts(
    status: dict[str, dict[str, Any]],
    *,
    distribution_check_passed: bool,
    installed_wheel_smoke_passed: bool,
    live_retrieval_passed: bool,
) -> bool:
    return not _evidence_flag_errors(
        status,
        distribution_check_passed=distribution_check_passed,
        installed_wheel_smoke_passed=installed_wheel_smoke_passed,
        live_retrieval_passed=live_retrieval_passed,
    )


def _evidence_flag_errors(
    status: dict[str, dict[str, Any]],
    *,
    distribution_check_passed: bool,
    installed_wheel_smoke_passed: bool,
    live_retrieval_passed: bool,
) -> dict[str, str]:
    expected = {
        "distribution_check": distribution_check_passed,
        "installed_wheel_smoke": installed_wheel_smoke_passed,
        "live_retrieval_smoke": live_retrieval_passed,
    }
    errors = {}
    for name, expected_passed in expected.items():
        artifact = status.get(name)
        if artifact is None:
            errors[name] = "artifact status is missing"
            continue
        state = artifact["result_state"]
        if expected_passed and state != "passed":
            errors[name] = f"flag says passed but artifact result_state is {state}"
        if not expected_passed and state == "passed":
            errors[name] = "flag says not passed but artifact result_state is passed"
    return errors


def _evidence_artifact_errors(status: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    expected_names = set(DEFAULT_EVIDENCE_ARTIFACTS)
    errors: dict[str, list[str]] = {}
    for missing_name in sorted(expected_names - set(status)):
        errors[missing_name] = ["artifact status is missing"]
    for unexpected_name in sorted(set(status) - expected_names):
        errors[unexpected_name] = ["unexpected evidence artifact"]
    for name, artifact in status.items():
        item_errors = []
        if not artifact["exists"]:
            item_errors.append("artifact file is missing")
        if not artifact["json_valid"]:
            detail = artifact["json_error"]
            item_errors.append(f"artifact JSON is invalid: {detail}" if detail else "artifact JSON is invalid")
        if not artifact["json_required_keys_present"]:
            missing_keys = ", ".join(artifact["missing_json_keys"])
            item_errors.append(f"artifact JSON is missing required keys: {missing_keys}")
        item_errors.extend(artifact["result_errors"])
        if item_errors:
            errors[name] = item_errors
    return errors


def _artifact_result(name: str, value: Any) -> tuple[str, list[str]]:
    if not isinstance(value, dict):
        return "unknown", ["artifact JSON must be an object"]
    if name == "distribution_check":
        return _distribution_check_result(value)
    if name == "installed_wheel_smoke":
        return _installed_wheel_smoke_result(value)
    if name == "live_retrieval_smoke":
        return _live_retrieval_smoke_result(value)
    if name == "release_manifest":
        return _release_manifest_result(value)
    return "unknown", []


def _distribution_check_result(value: dict[str, Any]) -> tuple[str, list[str]]:
    required_true_fields = (
        "required_modules_present",
        "required_entry_points_present",
        "wheel_metadata_present",
        "wheel_metadata_valid",
        "version_consistent",
        "sdist_required_files_present",
        "readme_entry_points_documented",
        "readme_release_reports_documented",
        "env_example_valid",
    )
    errors = _false_or_missing_fields(value, required_true_fields)
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts must contain at least one built distribution")
    if value.get("message") != "distribution artifact check passed":
        errors.append("message must report distribution artifact check passed")
    return ("failed" if errors else "passed", errors)


def _installed_wheel_smoke_result(value: dict[str, Any]) -> tuple[str, list[str]]:
    required_true_fields = (
        "installed",
        "console_scripts_checked",
        "offline_demo_ran",
        "summary_demo_ran",
        "output_file_written",
    )
    errors = _false_or_missing_fields(value, required_true_fields)
    if not isinstance(value.get("rows"), int) or value["rows"] <= 0:
        errors.append("rows must be a positive integer")
    if not isinstance(value.get("output_bytes"), int) or value["output_bytes"] <= 0:
        errors.append("output_bytes must be a positive integer")
    if value.get("message") != "installed wheel offline smoke passed":
        errors.append("message must report installed wheel offline smoke passed")
    return ("failed" if errors else "passed", errors)


def _live_retrieval_smoke_result(value: dict[str, Any]) -> tuple[str, list[str]]:
    if value.get("skipped") is True:
        errors = []
        if value.get("api_key_configured") is not False:
            errors.append("skipped live retrieval must report api_key_configured=false")
        if value.get("documents_fetched", 0) != 0:
            errors.append("skipped live retrieval must not report fetched documents")
        if value.get("message") != "PATENTSVIEW_API_KEY is not configured; live retrieval smoke skipped.":
            errors.append("message must report live retrieval skipped")
        return ("failed" if errors else "skipped", errors)

    required_true_fields = ("api_key_configured", "has_claims", "has_description")
    errors = _false_or_missing_fields(value, required_true_fields)
    if not isinstance(value.get("documents_fetched"), int) or value["documents_fetched"] <= 0:
        errors.append("documents_fetched must be a positive integer")
    if value.get("provider") != "patentsview":
        errors.append("provider must be patentsview")
    if value.get("message") != "live PatentsView retrieval smoke passed":
        errors.append("message must report live PatentsView retrieval smoke passed")
    return ("failed" if errors else "passed", errors)


def _release_manifest_result(value: dict[str, Any]) -> tuple[str, list[str]]:
    errors = []
    if value.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    if value.get("success") is not True:
        errors.append("success must be true")
    reports = value.get("reports")
    if not isinstance(reports, dict):
        errors.append("reports must be an object")
    else:
        expected_reports = {
            "distribution_check": "dist/distribution_check.json",
            "installed_wheel_smoke": "dist/installed_wheel_smoke.json",
            "live_retrieval_smoke": "dist/live_retrieval_smoke.json",
            "readiness": "dist/readiness_report.json",
        }
        for name, expected_path in expected_reports.items():
            if reports.get(name) != expected_path:
                errors.append(f"reports.{name} must be {expected_path}")
    steps = value.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps must contain release-gate step results")
    else:
        for index, step in enumerate(steps):
            errors.extend(_release_manifest_step_errors(index, step))
        step_names = {
            step["name"]
            for step in steps
            if isinstance(step, dict) and isinstance(step.get("name"), str)
        }
        missing_steps = sorted(REQUIRED_RELEASE_MANIFEST_STEPS - step_names)
        if missing_steps:
            errors.append(f"steps must include: {', '.join(missing_steps)}")
    return ("failed" if errors else "passed", errors)


def _release_manifest_step_errors(index: int, value: Any) -> list[str]:
    if not isinstance(value, dict):
        return [f"steps[{index}] must be an object"]
    errors = []
    if not isinstance(value.get("name"), str) or not value["name"].strip():
        errors.append(f"steps[{index}].name must be a non-empty string")
    if not isinstance(value.get("command"), list) or not value["command"]:
        errors.append(f"steps[{index}].command must be a non-empty list")
    if not isinstance(value.get("return_code"), int):
        errors.append(f"steps[{index}].return_code must be an integer")
    if value.get("passed") is not True:
        errors.append(f"steps[{index}].passed must be true")
    elapsed_seconds = value.get("elapsed_seconds")
    if not isinstance(elapsed_seconds, int | float) or elapsed_seconds < 0:
        errors.append(f"steps[{index}].elapsed_seconds must be a non-negative number")
    return errors


def _false_or_missing_fields(value: dict[str, Any], field_names: tuple[str, ...]) -> list[str]:
    return [f"{field_name} must be true" for field_name in field_names if value.get(field_name) is not True]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _grade(score: int) -> str:
    if score >= 95:
        return "production_ready_v0.1"
    if score >= 85:
        return "release_candidate"
    if score >= 70:
        return "beta"
    return "needs_work"


def _ship_decision(blockers: list[str], gaps: list[str]) -> str:
    if blockers:
        return "do_not_ship"
    if gaps:
        return "ship_keyless_v0.1_only_after_accepting_live_validation_gap"
    return "ship_v0.1"


def _summary(blockers: list[str], gaps: list[str]) -> str:
    if blockers:
        return "Required release checks are failing; do not ship this build."
    if gaps:
        return (
            "Keyless v0.1 release candidate is validated; live PatentsView retrieval "
            "still needs target-environment proof."
        )
    return "Production-ready v0.1 checks passed, including live PatentsView retrieval."


def _next_commands(blockers: list[str], gaps: list[str]) -> list[str]:
    if blockers:
        return ["patent-copilot-release-check"]
    if gaps:
        return ["PATENTSVIEW_API_KEY=... patent-copilot-release-check --require-live"]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
