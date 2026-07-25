from __future__ import annotations

import subprocess
import sys


COMMANDS = [
    [sys.executable, "scripts/validate.py"],
    [sys.executable, "-m", "patent_copilot.eval_cli"],
    [sys.executable, "-m", "patent_copilot.smoke_cli"],
]


def main() -> int:
    for command in COMMANDS:
        print(f"+ {' '.join(command)}")
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            return completed.returncode
    print("local ci checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

