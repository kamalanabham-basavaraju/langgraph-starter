from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)


class EnterProError(RuntimeError):
    """Raised when Enter Pro cannot apply the requested remediation."""


class EnterProClient:
    def __init__(self, url: str | None, api_key: str | None, timeout: float):
        self.url = url
        self.api_key = api_key
        self.timeout = timeout

    def execute(self, prompt: str, project_path: Path) -> dict[str, Any]:
        if not self.url:
            raise EnterProError("ENTERPRO_URL is not configured")
        if not project_path.is_dir():
            raise EnterProError(f"Employee Portal path does not exist: {project_path}")
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
        return payload
