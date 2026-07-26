import json
import os

from patent_copilot import readiness_cli


def test_readiness_report_scores_release_candidate_without_live_key(monkeypatch, tmp_path) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        distribution_check_passed=True,
        installed_wheel_smoke_passed=True,
        generated_at="2026-07-26T00:00:00Z",
    )

    assert report["score"] == 90
    assert report["max_score"] == 100
    assert report["schema_version"] == "1.12"
    assert report["package_version"] == "0.1.0"
    assert report["generated_at"] == "2026-07-26T00:00:00Z"
    assert report["evidence"] == {
        "release_gate_passed": True,
        "distribution_check_passed": True,
        "installed_wheel_smoke_passed": True,
        "live_retrieval_passed": False,
    }
    assert report["evidence_artifacts"] == {
        "distribution_check": "dist/distribution_check.json",
        "installed_wheel_smoke": "dist/installed_wheel_smoke.json",
        "live_retrieval_smoke": "dist/live_retrieval_smoke.json",
        "release_manifest": "dist/release_manifest.json",
    }
    assert report["evidence_artifact_errors"] == {}
    assert report["evidence_flag_errors"] == {}
    distribution_status = report["evidence_artifact_status"]["distribution_check"]
    assert distribution_status["path"] == "dist/distribution_check.json"
    assert distribution_status["exists"] is True
    assert distribution_status["size_bytes"] > 0
    assert distribution_status["json_valid"] is True
    assert distribution_status["json_error"] is None
    assert distribution_status["json_required_keys"] == [
        "artifacts",
        "env_example_valid",
        "message",
        "required_modules_present",
    ]
    assert distribution_status["json_required_keys_present"] is True
    assert distribution_status["missing_json_keys"] == []
    assert distribution_status["result_state"] == "passed"
    assert distribution_status["result_consistent"] is True
    assert distribution_status["result_errors"] == []
    assert report["grade"] == "release_candidate"
    assert report["summary"] == (
        "Keyless v0.1 release candidate is validated; live PatentsView retrieval "
        "still needs target-environment proof."
    )
    assert report["next_commands"] == [
        "PATENTSVIEW_API_KEY=... patent-copilot-release-check --require-live"
    ]
    assert report["blockers"] == []
    assert any(
        check["name"] == "mcp_runtime_dependency"
        and "mcp and pydantic" in check["detail"]
        and check["passed"] is True
        for check in report["checks"]
    )
    assert any(
        check["name"] == "evidence_artifact_integrity"
        and check["points"] == 0
        and check["passed"] is True
        and check["required"] is True
        for check in report["checks"]
    )
    assert any(
        check["name"] == "evidence_flag_consistency"
        and check["points"] == 0
        and check["passed"] is True
        and check["required"] is True
        for check in report["checks"]
    )
    assert report["gaps"] == [
        (
            "Live PatentsView retrieval smoke has not passed in this environment; "
            "configure PATENTSVIEW_API_KEY and run the live smoke."
        )
    ]


def test_readiness_report_does_not_trust_key_without_live_smoke(monkeypatch, tmp_path) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        distribution_check_passed=True,
        installed_wheel_smoke_passed=True,
    )

    assert report["score"] == 90
    assert report["grade"] == "release_candidate"


def test_readiness_report_marks_missing_evidence_artifacts(monkeypatch, tmp_path) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    (tmp_path / "dist" / "live_retrieval_smoke.json").unlink()

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        distribution_check_passed=True,
        installed_wheel_smoke_passed=True,
    )

    assert report["evidence_artifact_status"]["live_retrieval_smoke"] == {
        "path": "dist/live_retrieval_smoke.json",
        "exists": False,
        "size_bytes": 0,
        "json_valid": False,
        "json_error": None,
        "json_required_keys": ["api_key_configured", "message", "provider", "skipped"],
        "json_required_keys_present": False,
        "missing_json_keys": ["api_key_configured", "message", "provider", "skipped"],
        "result_state": "unknown",
        "result_errors": ["artifact JSON must be an object"],
        "result_consistent": False,
    }
    assert report["ship_decision"] == "do_not_ship"
    assert any("Release evidence artifacts must exist" in item for item in report["blockers"])
    assert report["evidence_artifact_errors"]["live_retrieval_smoke"] == [
        "artifact file is missing",
        "artifact JSON is invalid",
        "artifact JSON is missing required keys: api_key_configured, message, provider, skipped",
        "artifact JSON must be an object",
    ]


def test_readiness_report_marks_invalid_evidence_artifact_json(monkeypatch, tmp_path) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    (tmp_path / "dist" / "distribution_check.json").write_text("{", encoding="utf-8")

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        distribution_check_passed=True,
        installed_wheel_smoke_passed=True,
    )

    distribution_status = report["evidence_artifact_status"]["distribution_check"]
    assert distribution_status["exists"] is True
    assert distribution_status["json_valid"] is False
    assert distribution_status["json_error"]
    assert distribution_status["json_required_keys_present"] is False
    assert distribution_status["result_state"] == "unknown"
    assert distribution_status["result_consistent"] is False
    assert report["ship_decision"] == "do_not_ship"
    assert any("Release evidence artifacts must exist" in item for item in report["blockers"])
    assert any(
        error.startswith("artifact JSON is invalid:")
        for error in report["evidence_artifact_errors"]["distribution_check"]
    )


def test_readiness_report_marks_missing_evidence_artifact_json_keys(
    monkeypatch,
    tmp_path,
) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    (tmp_path / "dist" / "installed_wheel_smoke.json").write_text(
        '{"message": "installed wheel offline smoke passed"}\n',
        encoding="utf-8",
    )

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        distribution_check_passed=True,
        installed_wheel_smoke_passed=True,
    )

    installed_status = report["evidence_artifact_status"]["installed_wheel_smoke"]
    assert installed_status["json_valid"] is True
    assert installed_status["json_required_keys_present"] is False
    assert installed_status["missing_json_keys"] == [
        "console_scripts_checked",
        "installed",
        "offline_demo_ran",
        "summary_demo_ran",
    ]
    assert installed_status["result_state"] == "failed"
    assert installed_status["result_consistent"] is False
    assert report["ship_decision"] == "do_not_ship"
    assert any("Release evidence artifacts must exist" in item for item in report["blockers"])
    assert report["evidence_artifact_errors"]["installed_wheel_smoke"] == [
        (
            "artifact JSON is missing required keys: console_scripts_checked, installed, "
            "offline_demo_ran, summary_demo_ran"
        ),
        "installed must be true",
        "console_scripts_checked must be true",
        "offline_demo_ran must be true",
        "summary_demo_ran must be true",
        "output_file_written must be true",
        "rows must be a positive integer",
        "output_bytes must be a positive integer",
    ]


def test_readiness_report_requires_env_example_validation_in_distribution_artifact(
    monkeypatch,
    tmp_path,
) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    (tmp_path / "dist" / "distribution_check.json").write_text(
        json.dumps(
            {
                "message": "distribution artifact check passed",
                "artifacts": [
                    {
                        "path": "dist/patent_copilot-0.1.0-py3-none-any.whl",
                        "size_bytes": 1,
                        "sha256": "demo",
                    }
                ],
                "required_modules_present": True,
                "required_entry_points_present": True,
                "wheel_metadata_present": True,
                "wheel_metadata_valid": True,
                "version_consistent": True,
                "sdist_required_files_present": True,
                "readme_entry_points_documented": True,
                "readme_release_reports_documented": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        distribution_check_passed=True,
        installed_wheel_smoke_passed=True,
    )

    distribution_status = report["evidence_artifact_status"]["distribution_check"]
    assert distribution_status["json_required_keys_present"] is False
    assert distribution_status["missing_json_keys"] == ["env_example_valid"]
    assert distribution_status["result_state"] == "failed"
    assert report["ship_decision"] == "do_not_ship"
    assert report["evidence_artifact_errors"]["distribution_check"] == [
        "artifact JSON is missing required keys: env_example_valid",
        "env_example_valid must be true",
    ]


def test_readiness_report_requires_valid_release_manifest(monkeypatch, tmp_path) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    (tmp_path / "dist" / "release_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "success": False,
                "reports": {
                    "distribution_check": "dist/distribution_check.json",
                    "installed_wheel_smoke": "dist/installed_wheel_smoke.json",
                    "live_retrieval_smoke": "dist/live_retrieval_smoke.json",
                    "readiness": "dist/readiness_report.json",
                },
                "steps": [
                    {
                        "name": "unit_tests",
                        "command": ["python", "-m", "pytest"],
                        "return_code": 1,
                        "passed": False,
                        "elapsed_seconds": 0.1,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        distribution_check_passed=True,
        installed_wheel_smoke_passed=True,
    )

    manifest_status = report["evidence_artifact_status"]["release_manifest"]
    assert manifest_status["json_required_keys_present"] is True
    assert manifest_status["result_state"] == "failed"
    assert manifest_status["result_errors"] == [
        "success must be true",
        "steps[0].passed must be true",
        (
            "steps must include: build_artifacts, distribution_check, installed_wheel_smoke, "
            "lint, live_retrieval_smoke"
        ),
    ]
    assert report["ship_decision"] == "do_not_ship"
    assert any("Release evidence artifacts must exist" in item for item in report["blockers"])


def test_readiness_report_requires_release_manifest_core_steps(monkeypatch, tmp_path) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    (tmp_path / "dist" / "release_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "success": True,
                "reports": {
                    "distribution_check": "dist/distribution_check.json",
                    "installed_wheel_smoke": "dist/installed_wheel_smoke.json",
                    "live_retrieval_smoke": "dist/live_retrieval_smoke.json",
                    "readiness": "dist/readiness_report.json",
                },
                "steps": [
                    {
                        "name": "unit_tests",
                        "command": ["python", "-m", "pytest"],
                        "return_code": 0,
                        "passed": True,
                        "elapsed_seconds": 0.1,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        distribution_check_passed=True,
        installed_wheel_smoke_passed=True,
    )

    manifest_status = report["evidence_artifact_status"]["release_manifest"]
    assert manifest_status["result_state"] == "failed"
    assert manifest_status["result_errors"] == [
        (
            "steps must include: build_artifacts, distribution_check, installed_wheel_smoke, "
            "lint, live_retrieval_smoke"
        )
    ]
    assert report["ship_decision"] == "do_not_ship"


def test_readiness_report_scores_production_ready_with_live_smoke(monkeypatch, tmp_path) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    _write_live_passed_artifact(tmp_path)
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        distribution_check_passed=True,
        installed_wheel_smoke_passed=True,
        live_retrieval_passed=True,
    )

    assert report["score"] == 100
    assert report["grade"] == "production_ready_v0.1"
    assert report["ship_decision"] == "ship_v0.1"
    assert report["summary"] == (
        "Production-ready v0.1 checks passed, including live PatentsView retrieval."
    )
    assert report["next_commands"] == []
    assert report["evidence"]["live_retrieval_passed"] is True


def test_readiness_report_blocks_live_passed_flag_when_artifact_was_skipped(
    monkeypatch,
    tmp_path,
) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        distribution_check_passed=True,
        installed_wheel_smoke_passed=True,
        live_retrieval_passed=True,
    )

    assert report["score"] == 100
    assert report["grade"] == "production_ready_v0.1"
    assert report["ship_decision"] == "do_not_ship"
    assert any("Readiness evidence flags must match" in item for item in report["blockers"])
    assert report["evidence_artifact_errors"] == {}
    assert report["evidence_flag_errors"] == {
        "live_retrieval_smoke": "flag says passed but artifact result_state is skipped"
    }
    flag_check = next(
        check for check in report["checks"] if check["name"] == "evidence_flag_consistency"
    )
    assert flag_check["passed"] is False


def test_readiness_report_requires_release_gate(monkeypatch, tmp_path) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(os.environ, "PATENTSVIEW_API_KEY", "test-key")

    report = readiness_cli.build_readiness_report(
        release_gate_passed=False,
        distribution_check_passed=True,
        installed_wheel_smoke_passed=True,
        live_retrieval_passed=True,
    )

    assert report["ship_decision"] == "do_not_ship"
    assert report["summary"] == "Required release checks are failing; do not ship this build."
    assert report["next_commands"] == ["patent-copilot-release-check"]
    assert any("Release gate must pass" in item for item in report["blockers"])


def test_readiness_report_requires_distribution_check(monkeypatch, tmp_path) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        live_retrieval_passed=True,
    )

    assert report["ship_decision"] == "do_not_ship"
    assert any("Distribution artifact check must pass" in item for item in report["blockers"])


def test_readiness_report_requires_installed_wheel_smoke(monkeypatch, tmp_path) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")

    report = readiness_cli.build_readiness_report(
        release_gate_passed=True,
        distribution_check_passed=True,
        live_retrieval_passed=True,
    )

    assert report["ship_decision"] == "do_not_ship"
    assert any("Installed wheel smoke must pass" in item for item in report["blockers"])


def test_readiness_cli_writes_output_file(monkeypatch, tmp_path, capsys) -> None:
    _prepare_project_root(monkeypatch, tmp_path)
    output_path = tmp_path / "artifacts" / "readiness.json"

    exit_code = readiness_cli.main(
        [
            "--release-gate-passed",
            "--distribution-check-passed",
            "--installed-wheel-smoke-passed",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    stdout_report = json.loads(capsys.readouterr().out)
    file_report = json.loads(output_path.read_text(encoding="utf-8"))
    assert file_report == stdout_report
    assert file_report["schema_version"] == "1.12"
    assert file_report["package_version"] == "0.1.0"
    assert file_report["generated_at"].endswith("Z")
    assert file_report["evidence"]["release_gate_passed"] is True
    assert file_report["evidence_artifact_errors"] == {}
    assert file_report["evidence_flag_errors"] == {}
    assert file_report["evidence_artifacts"]["distribution_check"] == (
        "dist/distribution_check.json"
    )
    assert file_report["evidence_artifacts"]["release_manifest"] == "dist/release_manifest.json"
    assert file_report["evidence_artifact_status"]["installed_wheel_smoke"]["exists"] is True
    assert file_report["evidence_artifact_status"]["installed_wheel_smoke"]["json_valid"] is True
    assert (
        file_report["evidence_artifact_status"]["installed_wheel_smoke"][
            "json_required_keys_present"
        ]
        is True
    )
    assert file_report["score"] == 90


def _prepare_project_root(monkeypatch, tmp_path) -> None:
    (tmp_path / "README.md").write_text(
        "## MCP Response Contracts\nClients check the `ok` flag.\n\n"
        "## Legal Notice\nThis is not legal advice.\n",
        encoding="utf-8",
    )
    golden_dir = tmp_path / "examples" / "golden"
    golden_dir.mkdir(parents=True)
    for index in range(6):
        (golden_dir / f"fixture_{index}.json").write_text("{}", encoding="utf-8")
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "patent_copilot-0.1.0-py3-none-any.whl").write_text("", encoding="utf-8")
    (dist_dir / "distribution_check.json").write_text(
        json.dumps(
            {
                "message": "distribution artifact check passed",
                "artifacts": [
                    {
                        "path": "dist/patent_copilot-0.1.0-py3-none-any.whl",
                        "size_bytes": 1,
                        "sha256": "demo",
                    }
                ],
                "required_modules_present": True,
                "required_entry_points_present": True,
                "wheel_metadata_present": True,
                "wheel_metadata_valid": True,
                "version_consistent": True,
                "sdist_required_files_present": True,
                "readme_entry_points_documented": True,
                "readme_release_reports_documented": True,
                "env_example_valid": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (dist_dir / "installed_wheel_smoke.json").write_text(
        json.dumps(
            {
                "message": "installed wheel offline smoke passed",
                "installed": True,
                "console_scripts_checked": True,
                "offline_demo_ran": True,
                "summary_demo_ran": True,
                "output_file_written": True,
                "output_bytes": 1609,
                "rows": 3,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (dist_dir / "live_retrieval_smoke.json").write_text(
        json.dumps(
            {
                "message": "PATENTSVIEW_API_KEY is not configured; live retrieval smoke skipped.",
                "provider": "patentsview",
                "api_key_configured": False,
                "skipped": True,
                "documents_fetched": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (dist_dir / "release_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "success": True,
                "require_live": False,
                "api_key_configured": False,
                "patent_id": None,
                "reports": {
                    "distribution_check": "dist/distribution_check.json",
                    "installed_wheel_smoke": "dist/installed_wheel_smoke.json",
                    "live_retrieval_smoke": "dist/live_retrieval_smoke.json",
                    "readiness": "dist/readiness_report.json",
                },
                "steps": _release_manifest_steps(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(readiness_cli, "PROJECT_ROOT", tmp_path)


def _release_manifest_steps() -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "command": ["python", name],
            "return_code": 0,
            "passed": True,
            "elapsed_seconds": 0.1,
        }
        for name in [
            "unit_tests",
            "lint",
            "build_artifacts",
            "distribution_check",
            "installed_wheel_smoke",
            "live_retrieval_smoke",
        ]
    ]


def _write_live_passed_artifact(tmp_path) -> None:
    (tmp_path / "dist" / "live_retrieval_smoke.json").write_text(
        json.dumps(
            {
                "message": "live PatentsView retrieval smoke passed",
                "provider": "patentsview",
                "api_key_configured": True,
                "skipped": False,
                "documents_fetched": 1,
                "has_claims": True,
                "has_description": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
