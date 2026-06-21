from __future__ import annotations

import logging
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_NODE_BIN = REPO_ROOT / "node_modules" / ".bin"


class EnterProError(RuntimeError):
    """Raised when Enter Pro cannot apply the requested remediation."""


class EnterProClient:
    def __init__(
        self,
        url: str | None,
        api_key: str | None,
        command: str | None,
        workspace_id: str | None,
        timeout: float,
    ):
        self.url = url
        self.api_key = api_key
        self.command = command
        self.workspace_id = workspace_id or ""
        self.timeout = timeout

    def execute(self, prompt: str, project_path: Path) -> dict[str, Any]:
        if not project_path.is_dir():
            raise EnterProError(f"Employee Portal path does not exist: {project_path}")
        if self.command or not self.url:
            return self._execute_cli(prompt, project_path)
        return self._execute_http(prompt, project_path)

    def _execute_cli(self, prompt: str, project_path: Path) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="enterpro-") as temp_dir:
            prompt_file = Path(temp_dir) / "prompt.md"
            prompt_file.write_text(prompt, encoding="utf-8")
            args = self._command_args(prompt, prompt_file, project_path)
            if not args:
                raise EnterProError("ENTERPRO_COMMAND is empty after template rendering")
            env = os.environ.copy()
            env["PATH"] = self._path_with_local_node_bin(env)
            executable = args[0]
            if not Path(executable).exists() and shutil.which(executable, path=env["PATH"]) is None:
                raise EnterProError(
                    f"Enter CLI executable is not available on PATH: {executable}. "
                    "Run `python -m scripts.check_enter` in the same shell/container, "
                    "or set ENTERPRO_COMMAND to the full executable path."
                )
            if self.api_key:
                env["ENTER_API_KEY"] = self.api_key
                env["ENTERPRO_API_KEY"] = self.api_key
                env["ENTER_PRO_API_KEY"] = self.api_key
            if self.workspace_id:
                env["ENTERPRO_WORKSPACE_ID"] = self.workspace_id
                env["ENTER_PRO_WORKSPACE_ID"] = self.workspace_id
            try:
                completed = subprocess.run(
                    args,
                    cwd=project_path,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                logger.exception("Enter Pro CLI execution failed")
                raise EnterProError(f"Enter Pro CLI execution failed: {exc}") from exc
        result = {
            "mode": "cli",
            "command": self._redacted_command(args),
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-8000:],
            "stderr": completed.stderr[-8000:],
        }
        json_output = self._json_output(completed.stdout)
        if json_output is not None:
            result["json"] = json_output
        if completed.returncode != 0:
            raise EnterProError(f"Enter Pro CLI returned exit code {completed.returncode}: {result}")
        return result

    def _execute_http(self, prompt: str, project_path: Path) -> dict[str, Any]:
        if not self.url:
            raise EnterProError("Configure ENTERPRO_COMMAND for CLI mode or ENTERPRO_URL for HTTP mode")
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = requests.post(
                self.url,
                json={"prompt": prompt, "project_path": str(project_path)},
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.exception("Enter Pro execution failed")
            raise EnterProError(f"Enter Pro execution failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise EnterProError("Enter Pro returned an unsupported response shape")
        payload.setdefault("mode", "http")
        return payload

    def _command_args(self, prompt: str, prompt_file: Path, project_path: Path) -> list[str]:
        if self.command:
            command = self.command.format(
                prompt=prompt,
                prompt_file=str(prompt_file),
                project_path=str(project_path),
                workspace_id=self.workspace_id,
            )
            return shlex.split(command)

        args = [
            "enter",
            "-p",
            prompt,
            "-permission-mode",
            "acceptEdits",
            "-output-format",
            "json",
        ]
        if self.api_key:
            args.extend(["-api-key", self.api_key])
        if self.workspace_id:
            workspace_flag = "-workspace-id" if self.workspace_id.isdigit() else "-workspace"
            args.extend([workspace_flag, self.workspace_id])
        return args

    @staticmethod
    def _path_with_local_node_bin(env: dict[str, str]) -> str:
        current_path = env.get("PATH", "")
        if LOCAL_NODE_BIN.is_dir():
            return f"{LOCAL_NODE_BIN}{os.pathsep}{current_path}"
        return current_path

    @staticmethod
    def _json_output(stdout: str) -> Any | None:
        text = stdout.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    @staticmethod
    def _redacted_command(args: list[str]) -> list[str]:
        redacted = []
        redact_next = False
        for arg in args:
            lowered = arg.lower()
            if redact_next:
                redacted.append("***")
                redact_next = False
                continue
            if any(token in lowered for token in ("key=", "token=", "secret=")):
                redacted.append("***")
                continue
            redacted.append(arg)
            if lowered in {"-api-key", "--api-key", "--token", "--secret", "-p", "--print"}:
                redact_next = True
        return redacted
