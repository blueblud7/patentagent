from __future__ import annotations

import json
import subprocess
from pathlib import Path

from patent_copilot import installed_wheel_smoke_cli


def test_installed_wheel_smoke_defaults_to_current_directory(monkeypatch, tmp_path, capsys) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    _stub_venv(monkeypatch)
    _stub_run_success(monkeypatch)

    assert installed_wheel_smoke_cli.main([]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["project_root"] == str(tmp_path)
    assert output["installed"] is True
    assert output["console_scripts_checked"] is True
    assert output["offline_demo_ran"] is True
    assert output["summary_demo_ran"] is True
    assert output["output_file_written"] is True
    assert output["output_bytes"] > 0
    assert output["rows"] == 1


def test_installed_wheel_smoke_accepts_project_root(monkeypatch, tmp_path, capsys) -> None:
    project_root = tmp_path / "project"
    _prepare_project(project_root)
    monkeypatch.chdir(tmp_path)
    _stub_venv(monkeypatch)
    _stub_run_success(monkeypatch)

    assert installed_wheel_smoke_cli.main(["--project-root", str(project_root)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["project_root"] == str(project_root)
    assert output["wheel"].endswith("patent_copilot-0.1.0-py3-none-any.whl")


def test_installed_wheel_smoke_writes_output_file(monkeypatch, tmp_path, capsys) -> None:
    _prepare_project(tmp_path)
    output_path = tmp_path / "reports" / "installed_wheel.json"
    monkeypatch.chdir(tmp_path)
    _stub_venv(monkeypatch)
    _stub_run_success(monkeypatch)

    assert installed_wheel_smoke_cli.main(["--output", str(output_path)]) == 0

    stdout_output = json.loads(capsys.readouterr().out)
    file_output = json.loads(output_path.read_text(encoding="utf-8"))
    assert file_output == stdout_output
    assert file_output["installed"] is True
    assert file_output["console_scripts_checked"] is True


def test_installed_wheel_smoke_reports_missing_wheel(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert installed_wheel_smoke_cli.main([]) == 1

    output = json.loads(capsys.readouterr().out)
    assert output["wheel"] is None
    assert "No wheel found" in output["message"]


def test_installed_wheel_smoke_reports_timeout_as_json(monkeypatch, tmp_path, capsys) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    _stub_venv(monkeypatch)

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 124, stdout="", stderr="command timed out")

    monkeypatch.setattr(installed_wheel_smoke_cli, "_run", fake_run)

    assert installed_wheel_smoke_cli.main([]) == 124

    output = json.loads(capsys.readouterr().out)
    assert output["installed"] is False
    assert "wheel install failed" in output["message"]
    assert "command timed out" in output["message"]


def test_installed_wheel_smoke_reports_invalid_demo_json(monkeypatch, tmp_path, capsys) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    _stub_venv(monkeypatch)

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0].endswith("patent-copilot-demo"):
            return subprocess.CompletedProcess(command, 0, stdout="{", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(installed_wheel_smoke_cli, "_run", fake_run)

    assert installed_wheel_smoke_cli.main([]) == 1

    output = json.loads(capsys.readouterr().out)
    assert output["installed"] is True
    assert "invalid JSON" in output["message"]


def test_installed_wheel_smoke_reports_non_object_demo_json(monkeypatch, tmp_path, capsys) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    _stub_venv(monkeypatch)

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0].endswith("patent-copilot-demo"):
            return subprocess.CompletedProcess(command, 0, stdout="[]", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(installed_wheel_smoke_cli, "_run", fake_run)

    assert installed_wheel_smoke_cli.main([]) == 1

    output = json.loads(capsys.readouterr().out)
    assert output["installed"] is True
    assert "must be an object" in output["message"]


def test_installed_wheel_smoke_reports_missing_output_file(monkeypatch, tmp_path, capsys) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    _stub_venv(monkeypatch)

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if "--output" in command:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="wrote chart.csv")
        if command[0].endswith("patent-copilot-demo"):
            if "summary" in command:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps(
                        {
                            "review_summary": {
                                "total_rows": 1,
                                "review_flag_counts": {},
                            }
                        }
                    ),
                    stderr="",
                )
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"rows": [{"element_no": "1"}], "csv": "element_no\n1\n"}),
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(installed_wheel_smoke_cli, "_run", fake_run)

    assert installed_wheel_smoke_cli.main([]) == 1

    output = json.loads(capsys.readouterr().out)
    assert output["installed"] is True
    assert "did not create" in output["message"]


def _prepare_project(path: Path) -> None:
    (path / "dist").mkdir(parents=True)
    (path / "dist" / "patent_copilot-0.1.0-py3-none-any.whl").write_text("", encoding="utf-8")
    (path / "examples").mkdir()
    (path / "examples" / "build_claim_chart_request.json").write_text("{}", encoding="utf-8")


def _stub_venv(monkeypatch) -> None:
    class FakeEnvBuilder:
        def __init__(self, *, with_pip: bool) -> None:
            self.with_pip = with_pip

        def create(self, venv_dir: Path) -> None:
            (venv_dir / "bin").mkdir(parents=True)
            (venv_dir / "bin" / "python").write_text("", encoding="utf-8")
            (venv_dir / "bin" / "patent-copilot-demo").write_text("", encoding="utf-8")
            (venv_dir / "bin" / "patent-copilot-preflight").write_text("", encoding="utf-8")

    monkeypatch.setattr(installed_wheel_smoke_cli.venv, "EnvBuilder", FakeEnvBuilder)


def _stub_run_success(monkeypatch) -> None:
    calls = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if "--output" in command:
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_text(
                "element_no,role,claim_element,best_prior_art_id\n1,functional,processor,US-DEMO\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr=f"wrote {output_path}\n")
        if command[0].endswith("patent-copilot-demo"):
            if "summary" in command:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps(
                        {
                            "review_summary": {
                                "total_rows": 1,
                                "review_flag_counts": {"missing_terms": 1},
                            }
                        }
                    ),
                    stderr="",
                )
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"rows": [{"element_no": "1"}], "csv": "element_no\n1\n"}),
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(installed_wheel_smoke_cli, "_run", fake_run)
