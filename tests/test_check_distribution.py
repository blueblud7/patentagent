from zipfile import ZipFile

from scripts import check_distribution


def test_required_modules_include_every_console_script_target() -> None:
    required_modules = check_distribution._required_modules()

    assert "patent_copilot/server.py" in required_modules
    assert "patent_copilot/cli.py" in required_modules
    assert "patent_copilot/config.py" in required_modules
    assert "patent_copilot/contracts.py" in required_modules
    assert "patent_copilot/eval_cli.py" in required_modules
    assert "patent_copilot/preflight_cli.py" in required_modules
    assert "patent_copilot/smoke_cli.py" in required_modules
    assert "patent_copilot/installed_wheel_smoke_cli.py" in required_modules
    assert "patent_copilot/readiness_cli.py" in required_modules


def test_mismatched_entry_points_report_expected_and_actual_targets() -> None:
    mismatches = check_distribution._mismatched_entry_points(
        {
            "patent-copilot": "patent_copilot.server:main",
            "patent-copilot-demo": "patent_copilot.cli:wrong",
        }
    )

    assert mismatches == {
        "patent-copilot-demo": {
            "expected": "patent_copilot.cli:main",
            "actual": "patent_copilot.cli:wrong",
        }
    }


def test_missing_entry_point_callables_are_reported(tmp_path) -> None:
    wheel_path = tmp_path / "sample.whl"
    with ZipFile(wheel_path, "w") as wheel:
        for target in check_distribution.REQUIRED_ENTRY_POINTS.values():
            module = target.split(":", 1)[0]
            module_path = f"{module.replace('.', '/')}.py"
            source = "def main() -> int:\n    return 0\n"
            if module == "patent_copilot.cli":
                source = "def not_main() -> int:\n    return 0\n"
            wheel.writestr(module_path, source)

    with ZipFile(wheel_path) as wheel:
        missing = check_distribution._missing_entry_point_callables(wheel)

    assert missing == ["patent-copilot-demo"]


def test_distribution_requires_license_file() -> None:
    required_sdist_files = check_distribution._required_sdist_files()

    assert "LICENSE" in required_sdist_files
    assert ".env.example" in required_sdist_files


def test_env_example_errors_accept_expected_live_validation_template(tmp_path) -> None:
    env_path = tmp_path / ".env.example"
    env_path.write_text(
        "PATENTSVIEW_API_KEY=\n"
        "# Optional: choose a recent grant or publication with long-text endpoint coverage.\n"
        "PATENT_COPILOT_LIVE_PATENT_ID=US12000000B2",
        encoding="utf-8",
    )

    assert check_distribution._env_example_errors(env_path) == []


def test_env_example_errors_report_missing_live_validation_variables(tmp_path) -> None:
    env_path = tmp_path / ".env.example"
    env_path.write_text("PATENTSVIEW_API_KEY=\n", encoding="utf-8")

    errors = check_distribution._env_example_errors(env_path)

    assert ".env.example must include PATENT_COPILOT_LIVE_PATENT_ID=." in errors


def test_env_example_errors_report_unexpected_default_live_patent_id(tmp_path) -> None:
    env_path = tmp_path / ".env.example"
    env_path.write_text(
        "PATENTSVIEW_API_KEY=\nPATENT_COPILOT_LIVE_PATENT_ID=US20240000001A1",
        encoding="utf-8",
    )

    errors = check_distribution._env_example_errors(env_path)

    assert (
        ".env.example must set PATENT_COPILOT_LIVE_PATENT_ID='US12000000B2'; "
        "got 'US20240000001A1'."
    ) in errors


def test_distribution_requires_documented_scripts_and_examples() -> None:
    required_sdist_files = check_distribution._required_sdist_files()

    assert "scripts/validate.py" in required_sdist_files
    assert "scripts/smoke_live_retrieval.py" in required_sdist_files
    assert "scripts/smoke_mcp_integration.py" in required_sdist_files
    assert "scripts/write_release_manifest.py" in required_sdist_files
    assert "examples/build_claim_chart_request.json" in required_sdist_files
    assert "examples/build_claim_chart_by_ids_request.json" in required_sdist_files
    assert "examples/google_patents_sample.html" in required_sdist_files
    assert "examples/golden/sensor_classifier.json" in required_sdist_files


def test_missing_readme_entry_points_reports_undocumented_console_scripts(tmp_path) -> None:
    readme_path = tmp_path / "README.md"
    documented = sorted(check_distribution.REQUIRED_ENTRY_POINTS)[:-1]
    readme_path.write_text("\n".join(documented), encoding="utf-8")

    missing = check_distribution._missing_readme_entry_points(readme_path)

    assert missing == [max(check_distribution.REQUIRED_ENTRY_POINTS)]


def test_missing_readme_release_reports_reports_undocumented_artifacts(tmp_path) -> None:
    readme_path = tmp_path / "README.md"
    documented = sorted(check_distribution.REQUIRED_RELEASE_REPORTS)[:-1]
    readme_path.write_text("\n".join(documented), encoding="utf-8")

    missing = check_distribution._missing_readme_release_reports(readme_path)

    assert missing == [max(check_distribution.REQUIRED_RELEASE_REPORTS)]


def test_wheel_metadata_errors_accept_expected_metadata() -> None:
    metadata = """Metadata-Version: 2.4
Name: patent-copilot
Summary: MCP server for prior art search and evidence-grounded patent claim charts.
Keywords: claim-chart,mcp,patent,patentsview,prior-art
Classifier: Development Status :: 3 - Alpha
Classifier: Intended Audience :: Legal Industry
Classifier: License :: OSI Approved :: MIT License
Classifier: Programming Language :: Python :: 3
Classifier: Programming Language :: Python :: 3.11
Classifier: Topic :: Scientific/Engineering :: Information Analysis
License-Expression: MIT
License-File: LICENSE
Project-URL: Homepage, https://github.com/blueblud7/patentagent
Project-URL: Documentation, https://github.com/blueblud7/patentagent#readme
Project-URL: Issues, https://github.com/blueblud7/patentagent/issues
Requires-Python: >=3.11
Requires-Dist: httpx>=0.27.0
Requires-Dist: mcp>=1.0.0
Requires-Dist: pydantic>=2.0.0
"""
    wheel_names = {"patent_copilot-0.1.0.dist-info/licenses/LICENSE"}

    assert check_distribution._wheel_metadata_errors(metadata, wheel_names) == []


def test_wheel_metadata_errors_report_missing_runtime_dependency() -> None:
    metadata = """Metadata-Version: 2.4
Name: patent-copilot
Summary: MCP server for prior art search and evidence-grounded patent claim charts.
License-Expression: MIT
License-File: LICENSE
Requires-Python: >=3.11
Requires-Dist: httpx>=0.27.0
"""
    wheel_names = {"patent_copilot-0.1.0.dist-info/licenses/LICENSE"}

    errors = check_distribution._wheel_metadata_errors(metadata, wheel_names)

    assert "Requires-Dist must include mcp>=1.0.0." in errors
    assert "Requires-Dist must include pydantic>=2.0.0." in errors


def test_wheel_metadata_errors_report_missing_discovery_metadata() -> None:
    metadata = """Metadata-Version: 2.4
Name: patent-copilot
Summary: wrong
License-Expression: MIT
License-File: LICENSE
Requires-Python: >=3.11
Requires-Dist: httpx>=0.27.0
Requires-Dist: mcp>=1.0.0
Requires-Dist: pydantic>=2.0.0
"""
    wheel_names = {"patent_copilot-0.1.0.dist-info/licenses/LICENSE"}

    errors = check_distribution._wheel_metadata_errors(metadata, wheel_names)

    assert "Summary must match project description; got 'wrong'." in errors
    assert any(error.startswith("Keywords must include:") for error in errors)
    assert any(error.startswith("Classifiers must include:") for error in errors)
    assert any(error.startswith("Project-URL metadata must include:") for error in errors)


def test_wheel_metadata_errors_report_missing_license_file() -> None:
    metadata = """Metadata-Version: 2.4
Name: patent-copilot
Summary: MCP server for prior art search and evidence-grounded patent claim charts.
License-Expression: MIT
Requires-Python: >=3.11
Requires-Dist: httpx>=0.27.0
Requires-Dist: mcp>=1.0.0
Requires-Dist: pydantic>=2.0.0
"""

    errors = check_distribution._wheel_metadata_errors(metadata, set())

    assert "License-File must include LICENSE." in errors
    assert "Wheel must include LICENSE under .dist-info/licenses/." in errors


def test_version_errors_accept_consistent_versions(monkeypatch) -> None:
    monkeypatch.setattr(check_distribution, "_pyproject_version", lambda: "0.1.0")
    monkeypatch.setattr(check_distribution, "_package_init_version", lambda: "0.1.0")
    metadata = "Metadata-Version: 2.4\nName: patent-copilot\nVersion: 0.1.0\n"

    assert check_distribution._version_errors(metadata) == []


def test_version_errors_report_pyproject_and_package_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(check_distribution, "_pyproject_version", lambda: "0.1.0")
    monkeypatch.setattr(check_distribution, "_package_init_version", lambda: "0.2.0")
    metadata = "Metadata-Version: 2.4\nName: patent-copilot\nVersion: 0.1.0\n"

    errors = check_distribution._version_errors(metadata)

    assert "pyproject version '0.1.0' must match package __version__ '0.2.0'." in errors


def test_version_errors_report_wheel_metadata_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(check_distribution, "_pyproject_version", lambda: "0.1.0")
    monkeypatch.setattr(check_distribution, "_package_init_version", lambda: "0.1.0")
    metadata = "Metadata-Version: 2.4\nName: patent-copilot\nVersion: 0.2.0\n"

    errors = check_distribution._version_errors(metadata)

    assert "wheel metadata Version '0.2.0' must match pyproject version '0.1.0'." in errors


def test_artifact_metadata_reports_size_and_sha256(tmp_path) -> None:
    artifact = tmp_path / "artifact.whl"
    artifact.write_bytes(b"patent-copilot-artifact")

    metadata = check_distribution._artifact_metadata(artifact)

    assert metadata == {
        "path": str(artifact),
        "size_bytes": 23,
        "sha256": "50cf706f448da9dce5d49a89ac9786d8be959a95c6a4142f32ed4a15d0842a89",
    }


def test_finish_writes_distribution_report(tmp_path, capsys) -> None:
    output_path = tmp_path / "reports" / "distribution.json"
    status = {"message": "distribution artifact check passed", "artifacts": []}

    assert check_distribution._finish(status, output_path, 0) == 0

    assert '"distribution artifact check passed"' in capsys.readouterr().out
    assert output_path.read_text(encoding="utf-8").endswith("\n")
