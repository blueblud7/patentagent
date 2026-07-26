from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
import tempfile
import venv
from json import JSONDecodeError
from pathlib import Path

COMMAND_TIMEOUT_SECONDS = 60


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the built wheel and run the offline demo.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root containing dist/ and examples/. Defaults to the current directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the installed wheel smoke JSON result.",
    )
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()

    wheels = sorted(glob.glob(str(project_root / "dist" / "patent_copilot-*.whl")))
    status = {
        "wheel": wheels[-1] if wheels else None,
        "project_root": str(project_root),
        "installed": False,
        "console_scripts_checked": False,
        "offline_demo_ran": False,
        "summary_demo_ran": False,
        "output_file_written": False,
        "output_bytes": 0,
        "rows": 0,
        "message": "",
    }
    if not wheels:
        status["message"] = "No wheel found in dist/. Run `python -m build` first."
        return _finish(status, args.output, 1)

    with tempfile.TemporaryDirectory(prefix="patent-copilot-wheel-smoke-") as temp_dir:
        venv_dir = Path(temp_dir) / "venv"
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        python = _venv_python(venv_dir)
        install = _run([str(python), "-m", "pip", "install", "--no-deps", wheels[-1]])
        if install.returncode != 0:
            status["message"] = _command_failure("wheel install failed", install)
            return _finish(status, args.output, install.returncode)
        status["installed"] = True

        request_path = project_root / "examples" / "build_claim_chart_request.json"
        demo_command = _venv_script(venv_dir, "patent-copilot-demo")
        preflight_command = _venv_script(venv_dir, "patent-copilot-preflight")
        preflight = _run([str(preflight_command)])
        if preflight.returncode != 0:
            status["message"] = _command_failure("installed preflight console script failed", preflight)
            return _finish(status, args.output, preflight.returncode)
        status["console_scripts_checked"] = True

        demo = _run(
            [
                str(demo_command),
                str(request_path),
                "--format",
                "json",
            ]
        )
        if demo.returncode != 0:
            status["message"] = _command_failure("installed offline demo failed", demo)
            return _finish(status, args.output, demo.returncode)

        try:
            payload = json.loads(demo.stdout)
        except JSONDecodeError as exc:
            status["message"] = f"installed offline demo returned invalid JSON: {exc}"
            return _finish(status, args.output, 1)
        if not isinstance(payload, dict):
            status["message"] = "installed offline demo JSON output must be an object."
            return _finish(status, args.output, 1)
        status["rows"] = len(payload.get("rows", []))
        status["offline_demo_ran"] = status["rows"] > 0 and bool(payload.get("csv"))
        if not status["offline_demo_ran"]:
            status["message"] = "Installed offline demo returned no claim-chart rows or CSV output."
            return _finish(status, args.output, 1)

        summary_demo = _run(
            [
                str(demo_command),
                str(request_path),
                "--format",
                "summary",
            ]
        )
        if summary_demo.returncode != 0:
            status["message"] = _command_failure("installed offline demo summary failed", summary_demo)
            return _finish(status, args.output, summary_demo.returncode)
        try:
            summary_payload = json.loads(summary_demo.stdout)
        except JSONDecodeError as exc:
            status["message"] = f"installed offline demo summary returned invalid JSON: {exc}"
            return _finish(status, args.output, 1)
        summary = summary_payload.get("review_summary") if isinstance(summary_payload, dict) else None
        status["summary_demo_ran"] = (
            isinstance(summary, dict)
            and summary.get("total_rows") == status["rows"]
            and "review_flag_counts" in summary
        )
        if not status["summary_demo_ran"]:
            status["message"] = "Installed offline demo summary did not include expected review_summary."
            return _finish(status, args.output, 1)

        output_path = Path(temp_dir) / "chart.csv"
        output_demo = _run(
            [
                str(demo_command),
                str(request_path),
                "--format",
                "csv",
                "--output",
                str(output_path),
            ]
        )
        if output_demo.returncode != 0:
            status["message"] = _command_failure("installed offline demo --output failed", output_demo)
            return _finish(status, args.output, output_demo.returncode)
        if not output_path.exists():
            status["message"] = "Installed offline demo --output did not create the requested file."
            return _finish(status, args.output, 1)
        output_text = output_path.read_text(encoding="utf-8")
        status["output_bytes"] = len(output_text.encode("utf-8"))
        status["output_file_written"] = output_text.startswith(
            "element_no,role,claim_element,best_prior_art_id"
        )
        if not status["output_file_written"]:
            status["message"] = "Installed offline demo --output did not write expected CSV content."
            return _finish(status, args.output, 1)

    status["message"] = "installed wheel offline smoke passed"
    return _finish(status, args.output, 0)


def _finish(status: dict, output_path: Path | None, return_code: int) -> int:
    status_json = json.dumps(status, indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{status_json}\n", encoding="utf-8")
    print(status_json)
    return return_code


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or ""),
            stderr=f"command timed out after {COMMAND_TIMEOUT_SECONDS}s",
        )


def _venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_script(venv_dir: Path, name: str) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def _command_failure(prefix: str, completed: subprocess.CompletedProcess[str]) -> str:
    stderr = completed.stderr.strip()
    stdout = completed.stdout.strip()
    detail = stderr or stdout or f"exit code {completed.returncode}"
    return f"{prefix}: {detail}"


if __name__ == "__main__":
    raise SystemExit(main())
