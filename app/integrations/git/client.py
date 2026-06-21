from __future__ import annotations

import base64
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


class GitError(RuntimeError):
    """Raised when a local Git operation fails."""


class GitClient:
    def __init__(self, project_path: Path, require_clean: bool = True):
        self.project_path = project_path
        self.require_clean = require_clean

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        if shutil.which("git") is None:
            raise GitError("git executable is not installed or not available on PATH")
        try:
            return subprocess.run(
                ["git", *args], cwd=self.project_path, text=True, capture_output=True, check=check
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            stderr = getattr(exc, "stderr", None) or str(exc)
            if "dubious ownership" in stderr and "safe.directory" in stderr:
                raise GitError(
                    f"git {' '.join(args)} failed because Git does not trust {self.project_path}. "
                    f"Run `git config --global --add safe.directory {self.project_path}` in the runtime environment."
                ) from exc
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

    def create_incident_branch(
        self,
        incident: str,
        branch_source: str | None = None,
        base_branch: str | None = None,
        now: datetime | None = None,
    ) -> str:
        self.ensure_repository()
        changed = self.changed_files()
        if changed and self.require_clean:
            self.ensure_clean()
        if base_branch and not changed:
            self._switch_to_base(base_branch)
        source = branch_source or incident
        slug = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")[:48] or "incident"
        timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
        branch = f"ai/{timestamp}-{slug}"
        self._run("switch", "-c", branch)
        return branch

    def _switch_to_base(self, base_branch: str) -> None:
        remotes = self._run("remote", check=False).stdout.split()
        if "origin" in remotes:
            self._run("fetch", "origin", base_branch, check=False)
            if self._run("show-ref", "--verify", f"refs/heads/{base_branch}", check=False).returncode != 0:
                tracked = self._run(
                    "show-ref", "--verify", f"refs/remotes/origin/{base_branch}", check=False
                )
                if tracked.returncode != 0:
                    return
                self._run("switch", "-c", base_branch, "--track", f"origin/{base_branch}")
            else:
                self._run("switch", base_branch)
                self._run("pull", "--ff-only", "origin", base_branch, check=False)
            return
        if self._run("show-ref", "--verify", f"refs/heads/{base_branch}", check=False).returncode == 0:
            self._run("switch", base_branch)

    def changed_files(self) -> list[str]:
        output = self._run("status", "--porcelain").stdout
        return sorted({line[3:].strip().strip('"') for line in output.splitlines() if len(line) > 3})

    def commit_all(self, message: str) -> str:
        if not self.changed_files():
            raise GitError("Enter Pro produced no changes to commit")
        self._run("add", "--all")
        self._run("commit", "-m", message)
        return self._run("rev-parse", "HEAD").stdout.strip()

    def push_branch(self, branch_name: str, token: str | None = None) -> None:
        if not token:
            self._run("push", "--set-upstream", "origin", branch_name)
            return
        auth = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
        try:
            subprocess.run(
                [
                    "git",
                    "-c",
                    f"http.https://github.com/.extraheader=AUTHORIZATION: basic {auth}",
                    "push",
                    "--set-upstream",
                    "origin",
                    branch_name,
                ],
                cwd=self.project_path,
                text=True,
                capture_output=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            stderr = getattr(exc, "stderr", None) or str(exc)
            raise GitError(f"git push --set-upstream origin {branch_name} failed: {stderr.strip()}") from exc

    def create_pull_request(
        self,
        token: str,
        branch_name: str,
        base_branch: str,
        title: str,
        body: str,
        api_url: str = "https://api.github.com",
    ) -> dict[str, Any]:
        owner, repo = self._github_owner_repo()
        url = f"{api_url.rstrip('/')}/repos/{owner}/{repo}/pulls"
        response = requests.post(
            url,
            json={"title": title, "head": branch_name, "base": base_branch, "body": body},
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )
        if response.status_code == 422:
            existing = self._find_existing_pull_request(token, branch_name, base_branch, api_url)
            if existing:
                return existing
        try:
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise GitError(f"GitHub pull request creation failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise GitError("GitHub returned an unsupported pull request response")
        return payload

    def _find_existing_pull_request(
        self, token: str, branch_name: str, base_branch: str, api_url: str
    ) -> dict[str, Any] | None:
        owner, repo = self._github_owner_repo()
        url = f"{api_url.rstrip('/')}/repos/{owner}/{repo}/pulls"
        response = requests.get(
            url,
            params={"head": f"{owner}:{branch_name}", "base": base_branch, "state": "open"},
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )
        if not response.ok:
            return None
        payload = response.json()
        if isinstance(payload, list) and payload:
            return payload[0]
        return None

    def _github_owner_repo(self) -> tuple[str, str]:
        remote = self._run("remote", "get-url", "origin").stdout.strip()
        patterns = (
            r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
            r"github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
        )
        for pattern in patterns:
            match = re.search(pattern, remote)
            if match:
                return match.group("owner"), match.group("repo")
        raise GitError(f"Cannot parse GitHub owner/repo from origin remote: {remote}")
