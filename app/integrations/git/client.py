from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


class GitError(RuntimeError):
    """Raised when a local Git operation fails."""


class GitClient:
    def __init__(self, project_path: Path):
        self.project_path = project_path

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", *args], cwd=self.project_path, text=True, capture_output=True, check=check
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            stderr = getattr(exc, "stderr", None) or str(exc)
            raise GitError(f"git {' '.join(args)} failed: {stderr.strip()}") from exc

    def ensure_repository(self) -> None:
        self._run("rev-parse", "--is-inside-work-tree")

    def ensure_clean(self) -> None:
        changed = self.changed_files()
        if changed:
            raise GitError(
                "Target repository has pre-existing changes; refusing to mix them with an incident run: "
                + ", ".join(changed)
            )

    def create_incident_branch(self, incident: str, now: datetime | None = None) -> str:
        self.ensure_repository()
        self.ensure_clean()
        slug = re.sub(r"[^a-z0-9]+", "-", incident.lower()).strip("-")[:48] or "incident"
        timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
        branch = f"incident/{timestamp}-{slug}"
        self._run("switch", "-c", branch)
        return branch

    def changed_files(self) -> list[str]:
        output = self._run("status", "--porcelain").stdout
        return sorted({line[3:].strip().strip('"') for line in output.splitlines() if len(line) > 3})

    def commit_all(self, message: str) -> str:
        if not self.changed_files():
            raise GitError("Enter Pro produced no changes to commit")
        self._run("add", "--all")
        self._run("commit", "-m", message)
        return self._run("rev-parse", "HEAD").stdout.strip()
