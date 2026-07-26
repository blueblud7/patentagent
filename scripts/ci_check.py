from __future__ import annotations

import subprocess
import sys

COMMAND_TIMEOUT_SECONDS = 30

COMMANDS = [
    [sys.executable, "scripts/validate.py"],
    [sys.executable, "-m", "patent_copilot.eval_cli"],
    [sys.executable, "-m", "patent_copilot.preflight_cli"],
    [sys.executable, "-m", "patent_copilot.smoke_cli"],
    [sys.executable, "-m", "patent_copilot.mcp_integration_cli"],
]


def main() -> int:
    for command in COMMANDS:
        print(f"+ {' '.join(command)}")
        try:
            completed = subprocess.run(command, check=False, timeout=COMMAND_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            print(f"command timed out after {COMMAND_TIMEOUT_SECONDS}s: {' '.join(command)}")
            return 124
        if completed.returncode != 0:
            return completed.returncode
    print("local ci checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
