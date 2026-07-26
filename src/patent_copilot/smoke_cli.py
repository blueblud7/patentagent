from __future__ import annotations

import importlib.util
import json


def main() -> int:
    status = {
        "mcp_installed": importlib.util.find_spec("mcp") is not None,
        "server_importable": False,
        "tools_importable": False,
        "message": "",
    }

    try:
        from patent_copilot.tools.build_claim_chart import build_claim_chart_tool
        from patent_copilot.tools.search_prior_art import search_prior_art_tool

        assert build_claim_chart_tool
        assert search_prior_art_tool
        status["tools_importable"] = True
    except (ImportError, AssertionError) as exc:
        status["message"] = f"tool import failed: {exc}"
        print(json.dumps(status, indent=2))
        return 1

    if not status["mcp_installed"]:
        status["message"] = "mcp package is not installed; install project dependencies for server smoke."
        print(json.dumps(status, indent=2))
        return 0

    try:
        from patent_copilot import server

        assert server.mcp
        status["server_importable"] = True
        status["message"] = "server import smoke passed"
    except (ImportError, RuntimeError, AssertionError) as exc:
        status["message"] = f"server import failed: {exc}"
        print(json.dumps(status, indent=2))
        return 1

    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
