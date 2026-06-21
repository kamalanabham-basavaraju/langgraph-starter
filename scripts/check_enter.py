"""Check whether the Enter CLI is visible to the current runtime."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_NODE_BIN = REPO_ROOT / "node_modules" / ".bin"


def main() -> None:
    configured = os.getenv("ENTERPRO_COMMAND", "").strip()
    candidates = ["enter", "enterpro", "enter-code", "converge"]
    if configured:
        try:
            candidates.insert(0, shlex.split(configured)[0])
        except ValueError as exc:
            raise SystemExit(f"ENTERPRO_COMMAND cannot be parsed: {exc}") from exc

    seen: set[str] = set()
    found: list[tuple[str, str]] = []
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        search_path = os.environ.get("PATH", "")
        if LOCAL_NODE_BIN.is_dir():
            search_path = f"{LOCAL_NODE_BIN}{os.pathsep}{search_path}"
        resolved = candidate if Path(candidate).exists() else shutil.which(candidate, path=search_path)
        if resolved:
            found.append((candidate, str(resolved)))

    if not found:
        print("No Enter CLI executable found on PATH for this shell/container.")
        print("Open a fresh terminal after installing Enter, or set ENTERPRO_COMMAND to the full executable path.")
        raise SystemExit(1)

    for name, resolved in found:
        print(f"{name}: {resolved}")

    executable = found[0][1]
    try:
        result = subprocess.run(
            [executable, "--help"],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except OSError as exc:
        raise SystemExit(f"Failed to run {executable} --help: {exc}") from exc

    print("\n--- help output ---")
    print((result.stdout or result.stderr).strip())
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
