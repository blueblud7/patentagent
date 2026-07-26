from __future__ import annotations

import argparse
import ast
import configparser
import glob
import hashlib
import json
import tarfile
import tomllib
from email.parser import Parser
from pathlib import Path
from zipfile import ZipFile

REQUIRED_MODULES = {
    "patent_copilot/config.py",
    "patent_copilot/contracts.py",
    "patent_copilot/retrieval.py",
    "patent_copilot/tools/build_claim_chart.py",
    "patent_copilot/tools/search_prior_art.py",
}

REQUIRED_ENTRY_POINTS = {
    "patent-copilot": "patent_copilot.server:main",
    "patent-copilot-demo": "patent_copilot.cli:main",
    "patent-copilot-eval": "patent_copilot.eval_cli:main",
    "patent-copilot-smoke": "patent_copilot.smoke_cli:main",
    "patent-copilot-mcp-integration": "patent_copilot.mcp_integration_cli:main",
    "patent-copilot-live-retrieval-smoke": "patent_copilot.live_retrieval_cli:main",
    "patent-copilot-installed-wheel-smoke": "patent_copilot.installed_wheel_smoke_cli:main",
    "patent-copilot-preflight": "patent_copilot.preflight_cli:main",
    "patent-copilot-release-check": "patent_copilot.release_check_cli:main",
    "patent-copilot-readiness-audit": "patent_copilot.readiness_cli:main",
}

REQUIRED_PYTHON = ">=3.11"
REQUIRED_RUNTIME_DEPENDENCIES = {
    "httpx": ">=0.27.0",
    "mcp": ">=1.0.0",
    "pydantic": ">=2.0.0",
}
REQUIRED_DESCRIPTION = "MCP server for prior art search and evidence-grounded patent claim charts."
REQUIRED_KEYWORDS = {"claim-chart", "mcp", "patent", "patentsview", "prior-art"}
REQUIRED_CLASSIFIERS = {
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Legal Industry",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Topic :: Scientific/Engineering :: Information Analysis",
}
REQUIRED_PROJECT_URLS = {
    "Homepage": "https://github.com/blueblud7/patentagent",
    "Documentation": "https://github.com/blueblud7/patentagent#readme",
    "Issues": "https://github.com/blueblud7/patentagent/issues",
}

REQUIRED_RELEASE_REPORTS = {
    "dist/distribution_check.json",
    "dist/installed_wheel_smoke.json",
    "dist/readiness_report.json",
    "dist/live_retrieval_smoke.json",
    "dist/release_manifest.json",
}

REQUIRED_ENV_EXAMPLE_VALUES = {
    "PATENTSVIEW_API_KEY": "",
    "PATENT_COPILOT_LIVE_PATENT_ID": "US12000000B2",
}

REQUIRED_SDIST_STATIC_FILES = {
    ".env.example",
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "examples/build_claim_chart_by_ids_request.json",
    "examples/build_claim_chart_request.json",
    "examples/google_patents_sample.html",
    "examples/golden/abstract_only_warning.json",
    "examples/golden/battery_charger.json",
    "examples/golden/medical_pump_gap.json",
    "examples/golden/network_gateway.json",
    "examples/golden/robot_vacuum.json",
    "examples/golden/sensor_classifier.json",
    "scripts/check_distribution.py",
    "scripts/ci_check.py",
    "scripts/evaluate_golden.py",
    "scripts/readiness_audit.py",
    "scripts/release_check.py",
    "scripts/smoke_installed_wheel.py",
    "scripts/smoke_live_retrieval.py",
    "scripts/smoke_mcp.py",
    "scripts/smoke_mcp_integration.py",
    "scripts/validate.py",
    "scripts/write_release_manifest.py",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate v0.1 distribution artifacts.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the distribution check JSON result.",
    )
    args = parser.parse_args(argv)
    wheels = sorted(glob.glob("dist/patent_copilot-*.whl"))
    sdists = sorted(glob.glob("dist/patent_copilot-*.tar.gz"))
    status = {
        "wheel": wheels[-1] if wheels else None,
        "sdist": sdists[-1] if sdists else None,
        "artifacts": [],
        "required_modules_present": False,
        "required_entry_points_present": False,
        "wheel_metadata_present": False,
        "wheel_metadata_valid": False,
        "version_consistent": False,
        "sdist_required_files_present": False,
        "readme_entry_points_documented": False,
        "readme_release_reports_documented": False,
        "env_example_valid": False,
        "missing_modules": [],
        "missing_entry_points": [],
        "mismatched_entry_points": {},
        "missing_entry_point_callables": [],
        "metadata_errors": [],
        "version_errors": [],
        "missing_sdist_files": [],
        "missing_readme_entry_points": [],
        "missing_readme_release_reports": [],
        "env_example_errors": [],
        "message": "",
    }
    if not wheels:
        status["message"] = "No wheel found in dist/. Run `python -m build` first."
        return _finish(status, args.output, 1)
    if not sdists:
        status["message"] = "No sdist found in dist/. Run `python -m build` first."
        return _finish(status, args.output, 1)

    wheel_path = Path(wheels[-1])
    sdist_path = Path(sdists[-1])
    status["artifacts"] = [_artifact_metadata(wheel_path), _artifact_metadata(sdist_path)]
    with ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())
        required_modules = _required_modules()
        missing_modules = sorted(required_modules - names)
        status["missing_modules"] = missing_modules
        status["required_modules_present"] = not missing_modules

        entry_points_path = _entry_points_path(names)
        if entry_points_path is None:
            status["missing_entry_points"] = sorted(REQUIRED_ENTRY_POINTS)
            status["mismatched_entry_points"] = dict(REQUIRED_ENTRY_POINTS)
        else:
            parser = configparser.ConfigParser()
            parser.read_string(wheel.read(entry_points_path).decode("utf-8"))
            console_scripts = (
                dict(parser["console_scripts"]) if parser.has_section("console_scripts") else {}
            )
            status["missing_entry_points"] = sorted(set(REQUIRED_ENTRY_POINTS) - set(console_scripts))
            status["mismatched_entry_points"] = _mismatched_entry_points(console_scripts)
            status["missing_entry_point_callables"] = _missing_entry_point_callables(wheel)
        status["required_entry_points_present"] = not (
            status["missing_entry_points"]
            or status["mismatched_entry_points"]
            or status["missing_entry_point_callables"]
        )
        metadata_path = _metadata_path(names)
        status["wheel_metadata_present"] = metadata_path is not None
        if metadata_path is None:
            status["metadata_errors"] = ["Wheel METADATA file is missing."]
        else:
            metadata_errors = _wheel_metadata_errors(wheel.read(metadata_path).decode("utf-8"), names)
            status["metadata_errors"] = metadata_errors
            status["wheel_metadata_valid"] = not metadata_errors
            version_errors = _version_errors(wheel.read(metadata_path).decode("utf-8"))
            status["version_errors"] = version_errors
            status["version_consistent"] = not version_errors

    with tarfile.open(sdist_path, "r:gz") as sdist:
        names = set(sdist.getnames())
        required_sdist_files = _required_sdist_files()
        missing_sdist_files = sorted(
            item for item in required_sdist_files if not _sdist_contains(names, item)
        )
        status["missing_sdist_files"] = missing_sdist_files
        status["sdist_required_files_present"] = not missing_sdist_files

    missing_readme_entry_points = _missing_readme_entry_points()
    status["missing_readme_entry_points"] = missing_readme_entry_points
    status["readme_entry_points_documented"] = not missing_readme_entry_points
    missing_readme_release_reports = _missing_readme_release_reports()
    status["missing_readme_release_reports"] = missing_readme_release_reports
    status["readme_release_reports_documented"] = not missing_readme_release_reports
    env_example_errors = _env_example_errors()
    status["env_example_errors"] = env_example_errors
    status["env_example_valid"] = not env_example_errors

    if (
        status["required_modules_present"]
        and status["required_entry_points_present"]
        and status["wheel_metadata_present"]
        and status["wheel_metadata_valid"]
        and status["version_consistent"]
        and status["sdist_required_files_present"]
        and status["readme_entry_points_documented"]
        and status["readme_release_reports_documented"]
        and status["env_example_valid"]
    ):
        status["message"] = "distribution artifact check passed"
        return _finish(status, args.output, 0)

    status["message"] = "distribution artifact check failed"
    return _finish(status, args.output, 1)


def _finish(status: dict, output_path: Path | None, return_code: int) -> int:
    status_json = json.dumps(status, indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{status_json}\n", encoding="utf-8")
    print(status_json)
    return return_code


def _artifact_metadata(path: Path) -> dict[str, str | int]:
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _entry_points_path(names: set[str]) -> str | None:
    for name in names:
        if name.endswith(".dist-info/entry_points.txt"):
            return name
    return None


def _metadata_path(names: set[str]) -> str | None:
    for name in names:
        if name.endswith(".dist-info/METADATA"):
            return name
    return None


def _required_modules() -> set[str]:
    entry_point_modules = {
        f"{target.split(':', 1)[0].replace('.', '/')}.py"
        for target in REQUIRED_ENTRY_POINTS.values()
    }
    return REQUIRED_MODULES | entry_point_modules


def _required_sdist_files() -> set[str]:
    return REQUIRED_SDIST_STATIC_FILES | {f"src/{module}" for module in _required_modules()}


def _mismatched_entry_points(console_scripts: dict[str, str]) -> dict[str, dict[str, str]]:
    mismatches = {}
    for name, expected_target in REQUIRED_ENTRY_POINTS.items():
        actual_target = console_scripts.get(name)
        if actual_target is not None and actual_target != expected_target:
            mismatches[name] = {"expected": expected_target, "actual": actual_target}
    return mismatches


def _missing_entry_point_callables(wheel: ZipFile) -> list[str]:
    missing = []
    for name, target in REQUIRED_ENTRY_POINTS.items():
        module, function = target.split(":", 1)
        module_path = f"{module.replace('.', '/')}.py"
        try:
            source = wheel.read(module_path).decode("utf-8")
        except KeyError:
            missing.append(name)
            continue
        tree = ast.parse(source)
        functions = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        if function not in functions:
            missing.append(name)
    return sorted(missing)


def _wheel_metadata_errors(metadata_text: str, wheel_names: set[str]) -> list[str]:
    metadata = Parser().parsestr(metadata_text)
    errors = []
    if metadata.get("Name") != "patent-copilot":
        errors.append(f"Name must be patent-copilot; got {metadata.get('Name')!r}.")
    if metadata.get("Summary") != REQUIRED_DESCRIPTION:
        errors.append(f"Summary must match project description; got {metadata.get('Summary')!r}.")
    if metadata.get("Requires-Python") != REQUIRED_PYTHON:
        errors.append(
            f"Requires-Python must be {REQUIRED_PYTHON}; got {metadata.get('Requires-Python')!r}."
        )
    if metadata.get("License-Expression") != "MIT":
        errors.append(
            f"License-Expression must be MIT; got {metadata.get('License-Expression')!r}."
        )
    license_files = metadata.get_all("License-File", [])
    if "LICENSE" not in license_files:
        errors.append("License-File must include LICENSE.")
    if not any(name.endswith(".dist-info/licenses/LICENSE") for name in wheel_names):
        errors.append("Wheel must include LICENSE under .dist-info/licenses/.")

    requires_dist = metadata.get_all("Requires-Dist", [])
    for package, specifier in REQUIRED_RUNTIME_DEPENDENCIES.items():
        expected = f"{package}{specifier}"
        if not any(_requires_dist_matches(item, package, specifier) for item in requires_dist):
            errors.append(f"Requires-Dist must include {expected}.")
    keywords = {
        keyword.strip()
        for keyword in (metadata.get("Keywords") or "").split(",")
        if keyword.strip()
    }
    missing_keywords = sorted(REQUIRED_KEYWORDS - keywords)
    if missing_keywords:
        errors.append(f"Keywords must include: {', '.join(missing_keywords)}.")
    classifiers = set(metadata.get_all("Classifier", []))
    missing_classifiers = sorted(REQUIRED_CLASSIFIERS - classifiers)
    if missing_classifiers:
        errors.append(f"Classifiers must include: {', '.join(missing_classifiers)}.")
    project_urls = _project_urls(metadata.get_all("Project-URL", []))
    missing_project_urls = {
        name: url
        for name, url in REQUIRED_PROJECT_URLS.items()
        if project_urls.get(name) != url
    }
    if missing_project_urls:
        expected = ", ".join(f"{name}={url}" for name, url in sorted(missing_project_urls.items()))
        errors.append(f"Project-URL metadata must include: {expected}.")
    return errors


def _version_errors(metadata_text: str) -> list[str]:
    pyproject_version = _pyproject_version()
    package_version = _package_init_version()
    metadata_version = Parser().parsestr(metadata_text).get("Version")

    errors = []
    if pyproject_version != package_version:
        errors.append(
            f"pyproject version {pyproject_version!r} must match package __version__ "
            f"{package_version!r}."
        )
    if metadata_version != pyproject_version:
        errors.append(
            f"wheel metadata Version {metadata_version!r} must match pyproject version "
            f"{pyproject_version!r}."
        )
    return errors


def _missing_readme_entry_points(path: Path = Path("README.md")) -> list[str]:
    if not path.exists():
        return sorted(REQUIRED_ENTRY_POINTS)
    content = path.read_text(encoding="utf-8")
    return sorted(name for name in REQUIRED_ENTRY_POINTS if name not in content)


def _missing_readme_release_reports(path: Path = Path("README.md")) -> list[str]:
    if not path.exists():
        return sorted(REQUIRED_RELEASE_REPORTS)
    content = path.read_text(encoding="utf-8")
    return sorted(name for name in REQUIRED_RELEASE_REPORTS if name not in content)


def _env_example_errors(path: Path = Path(".env.example")) -> list[str]:
    if not path.exists():
        return [".env.example is missing."]
    values = _env_file_values(path)
    errors = []
    for key, expected_value in REQUIRED_ENV_EXAMPLE_VALUES.items():
        if key not in values:
            errors.append(f".env.example must include {key}=.")
        elif values[key] != expected_value:
            errors.append(
                f".env.example must set {key}={expected_value!r}; got {values[key]!r}."
            )
    return errors


def _env_file_values(path: Path) -> dict[str, str]:
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _pyproject_version(path: Path = Path("pyproject.toml")) -> str:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _package_init_version(path: Path = Path("src/patent_copilot/__init__.py")) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise RuntimeError("Could not find patent_copilot.__version__.")


def _requires_dist_matches(value: str, package: str, specifier: str) -> bool:
    normalized = value.replace(" ", "")
    return normalized == f"{package}{specifier}"


def _project_urls(values: list[str]) -> dict[str, str]:
    urls = {}
    for value in values:
        if "," not in value:
            continue
        name, url = value.split(",", 1)
        urls[name.strip()] = url.strip()
    return urls


def _sdist_contains(names: set[str], path: str) -> bool:
    suffix = f"/{path}"
    return any(name.endswith(suffix) for name in names)


if __name__ == "__main__":
    raise SystemExit(main())
