from __future__ import annotations

import importlib.util
import json
import sys

from patent_copilot.config import env_has_value, get_env_value

MIN_RUNTIME = (3, 11)
DEFAULT_PREFLIGHT_LIVE_PATENT_ID = "US12000000B2"


def main() -> int:
    status = build_preflight_status()
    print(json.dumps(status, indent=2))
    return 0 if status["python"]["ok_for_package_install"] else 2


def build_preflight_status() -> dict:
    python_ok = sys.version_info >= MIN_RUNTIME
    has_patentsview_key = env_has_value("PATENTSVIEW_API_KEY")
    live_patent_id = get_env_value("PATENT_COPILOT_LIVE_PATENT_ID") or DEFAULT_PREFLIGHT_LIVE_PATENT_ID
    mcp_installed = importlib.util.find_spec("mcp") is not None
    httpx_installed = importlib.util.find_spec("httpx") is not None
    pydantic_installed = importlib.util.find_spec("pydantic") is not None
    status = {
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "required": ">=3.11",
            "ok_for_package_install": python_ok,
        },
        "dependencies": {
            "mcp_installed": mcp_installed,
            "httpx_installed": httpx_installed,
            "pydantic_installed": pydantic_installed,
            "pytest_installed": importlib.util.find_spec("pytest") is not None,
        },
        "capabilities": {
            "offline_claim_chart": True,
            "golden_eval": True,
            "mcp_server_runtime": python_ok and mcp_installed and pydantic_installed,
            "live_patent_fetch": python_ok and httpx_installed,
            "patentsview_api_key_configured": has_patentsview_key,
        },
        "live_validation": {
            "api_key_env": "PATENTSVIEW_API_KEY",
            "api_key_configured": has_patentsview_key,
            "patent_id_env": "PATENT_COPILOT_LIVE_PATENT_ID",
            "patent_id": live_patent_id,
            "strict_command": (
                "PATENTSVIEW_API_KEY=... "
                f"patent-copilot-release-check --require-live --patent-id {live_patent_id}"
            ),
        },
        "next_steps": [],
    }
    if not has_patentsview_key:
        status["next_steps"].append(
            "Set PATENTSVIEW_API_KEY, then run `patent-copilot-release-check --require-live` "
            "for production_ready_v0.1 validation."
        )
    return status

if __name__ == "__main__":
    raise SystemExit(main())
