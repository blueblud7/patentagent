import json

import pytest

from patent_copilot import release_check_cli


@pytest.fixture(autouse=True)
def release_manifest_path(monkeypatch, tmp_path):
    path = tmp_path / "release_manifest.json"
    monkeypatch.setattr(release_check_cli, "RELEASE_MANIFEST_PATH", str(path))
    return path


def test_release_check_passes_live_flag_only_after_keyed_live_smoke(monkeypatch) -> None:
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(release_check_cli, "_run", fake_run)

    assert release_check_cli.main([]) == 0

    assert commands[-2] == release_check_cli.LIVE_RETRIEVAL_COMMAND
    assert release_check_cli.LIVE_RETRIEVAL_REPORT_PATH in commands[-2]
    assert [
        release_check_cli.sys.executable,
        "scripts/smoke_installed_wheel.py",
        "--output",
        release_check_cli.INSTALLED_WHEEL_SMOKE_REPORT_PATH,
    ] in commands
    assert commands[-1] == [
        release_check_cli.sys.executable,
        "scripts/readiness_audit.py",
        "--release-gate-passed",
        "--distribution-check-passed",
        "--installed-wheel-smoke-passed",
        "--output",
        release_check_cli.READINESS_REPORT_PATH,
        "--live-retrieval-passed",
    ]


def test_release_check_keeps_readiness_keyless_when_live_smoke_skips(
    monkeypatch,
    release_manifest_path,
) -> None:
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(release_check_cli, "_run", fake_run)

    assert release_check_cli.main([]) == 0

    assert commands[-2] == release_check_cli.LIVE_RETRIEVAL_COMMAND
    assert release_check_cli.LIVE_RETRIEVAL_REPORT_PATH in commands[-2]
    assert [
        release_check_cli.sys.executable,
        "scripts/smoke_installed_wheel.py",
        "--output",
        release_check_cli.INSTALLED_WHEEL_SMOKE_REPORT_PATH,
    ] in commands
    assert commands[-1] == [
        release_check_cli.sys.executable,
        "scripts/readiness_audit.py",
        "--release-gate-passed",
        "--distribution-check-passed",
        "--installed-wheel-smoke-passed",
        "--output",
        release_check_cli.READINESS_REPORT_PATH,
    ]
    manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0"
    assert manifest["success"] is True
    assert manifest["require_live"] is False
    assert manifest["api_key_configured"] is False
    assert manifest["patent_id"] is None
    assert manifest["reports"]["readiness"] == release_check_cli.READINESS_REPORT_PATH
    assert [step["name"] for step in manifest["steps"]] == [
        "unit_tests",
        "lint",
        "local_ci",
        "build_artifacts",
        "distribution_check",
        "installed_wheel_smoke",
        "live_retrieval_smoke",
        "readiness_audit",
    ]
    assert all(step["passed"] is True for step in manifest["steps"])
    assert all(isinstance(step["elapsed_seconds"], float) for step in manifest["steps"])
    assert all(step["elapsed_seconds"] >= 0 for step in manifest["steps"])


def test_release_check_treats_blank_api_key_as_keyless(monkeypatch) -> None:
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "   ")
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(release_check_cli, "_run", fake_run)

    assert release_check_cli.main([]) == 0

    assert commands[-1] == [
        release_check_cli.sys.executable,
        "scripts/readiness_audit.py",
        "--release-gate-passed",
        "--distribution-check-passed",
        "--installed-wheel-smoke-passed",
        "--output",
        release_check_cli.READINESS_REPORT_PATH,
    ]


def test_release_check_fails_before_readiness_when_live_smoke_fails(monkeypatch) -> None:
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> int:
        commands.append(command)
        if command == release_check_cli.LIVE_RETRIEVAL_COMMAND:
            return 1
        return 0

    monkeypatch.setattr(release_check_cli, "_run", fake_run)

    assert release_check_cli.main([]) == 1
    assert commands[-1] == release_check_cli.LIVE_RETRIEVAL_COMMAND


def test_release_check_require_live_uses_strict_live_smoke(monkeypatch) -> None:
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(release_check_cli, "_run", fake_run)

    assert release_check_cli.main(["--require-live"]) == 0

    assert commands[-2] == release_check_cli.STRICT_LIVE_RETRIEVAL_COMMAND
    assert release_check_cli.LIVE_RETRIEVAL_REPORT_PATH in commands[-2]
    assert commands[-1][-1] == "--live-retrieval-passed"


def test_release_check_passes_patent_id_to_live_smoke(monkeypatch) -> None:
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(release_check_cli, "_run", fake_run)

    assert release_check_cli.main(["--require-live", "--patent-id", "US20240000001A1"]) == 0

    assert commands[-2] == [
        *release_check_cli.STRICT_LIVE_RETRIEVAL_COMMAND,
        "--patent-id",
        "US20240000001A1",
    ]


def test_release_check_rejects_blank_patent_id_before_running_commands(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(release_check_cli, "_run", fake_run)

    try:
        release_check_cli.main(["--require-live", "--patent-id", "   "])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("blank --patent-id should fail argument parsing")

    assert commands == []
    assert "--patent-id must not be blank" in capsys.readouterr().err


def test_release_check_require_live_fails_before_running_commands_when_key_missing(
    monkeypatch,
    capsys,
    release_manifest_path,
) -> None:
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> int:
        commands.append(command)
        return 0

    monkeypatch.setattr(release_check_cli, "_run", fake_run)

    assert release_check_cli.main(["--require-live"]) == 2
    assert commands == []
    assert "PATENTSVIEW_API_KEY is required" in capsys.readouterr().out
    manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0"
    assert manifest["success"] is False
    assert manifest["require_live"] is True
    assert manifest["api_key_configured"] is False
    assert manifest["steps"] == []
    assert manifest["failure_reason"] == "PATENTSVIEW_API_KEY is required for strict live validation."
