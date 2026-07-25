from __future__ import annotations

import importlib.util
import json
import sys


MIN_RUNTIME = (3, 11)


def main() -> int:
    python_ok = sys.version_info >= MIN_RUNTIME
    status = {
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "required": ">=3.11",
            "ok_for_package_install": python_ok,
        },
        "dependencies": {
            "mcp_installed": importlib.util.find_spec("mcp") is not None,
            "httpx_installed": importlib.util.find_spec("httpx") is not None,
            "pytest_installed": importlib.util.find_spec("pytest") is not None,
        },
        "capabilities": {
            "offline_claim_chart": True,
            "golden_eval": True,
            "mcp_server_runtime": python_ok and importlib.util.find_spec("mcp") is not None,
            "live_patent_fetch": python_ok and importlib.util.find_spec("httpx") is not None,
        },
    }
    print(json.dumps(status, indent=2))
    return 0 if python_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

