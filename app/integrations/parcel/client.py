from __future__ import annotations

import logging
from typing import Any

import requests

from app.models.incident import ParcelDocument

logger = logging.getLogger(__name__)


class ParcelError(RuntimeError):
    """Raised when Parcel memory cannot be searched."""


class ParcelClient:
    def __init__(self, base_url: str | None, search_path: str, api_key: str | None, timeout: float):
        self.base_url = base_url
        self.search_path = search_path
        self.api_key = api_key
        self.timeout = timeout

    def search(self, query: str, limit: int = 8) -> list[ParcelDocument]:
        if not self.base_url:
            raise ParcelError("PARCEL_BASE_URL is not configured")
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = f"{self.base_url.rstrip('/')}/{self.search_path.lstrip('/')}"
        try:
            response = requests.post(
                url, json={"query": query, "limit": limit}, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            payload: Any = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.exception("Parcel search failed", extra={"url": url})
            raise ParcelError(f"Parcel search failed: {exc}") from exc

        raw_documents = payload.get("documents", payload.get("results", [])) if isinstance(payload, dict) else payload
        if not isinstance(raw_documents, list):
            raise ParcelError("Parcel returned an unsupported response shape")
        return [self._normalize(item) for item in raw_documents if isinstance(item, dict)]

    @staticmethod
    def _normalize(item: dict[str, Any]) -> ParcelDocument:
        return ParcelDocument(
            title=str(item.get("title") or item.get("name") or "Untitled"),
            content=str(item.get("content") or item.get("text") or item.get("snippet") or ""),
            reference=item.get("reference") or item.get("url") or item.get("id"),
            metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
        )
