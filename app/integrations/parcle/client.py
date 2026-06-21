from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.models.incident import ParcleDocument, ParcleMemoryDocument

logger = logging.getLogger(__name__)


class ParcleError(RuntimeError):
    """Raised when a Parcle memory operation fails."""


class ParcleClient:
    def __init__(
        self,
        api_key: str | None,
        user_id: str = "system_user",
        sdk_client: Any | None = None,
    ):
        self.api_key = api_key
        self.user_id = user_id
        self._client = sdk_client
        self._user_checked = False

    @property
    def memory_location(self) -> str:
        return f"parcle-sdk user:{self.user_id}"

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                from parcle import Parcle
            except ImportError as exc:
                raise ParcleError("The Parcle SDK is not installed. Run `pip install parcle`.") from exc
            self._client = Parcle(api_key=self.api_key) if self.api_key else Parcle()
        return self._client

    def ensure_user(self) -> None:
        if self._user_checked:
            return
        try:
            self.client.create_user(user_id=self.user_id)
        except Exception as exc:  # Parcle SDK exception types are not part of the public snippet.
            message = str(exc).lower()
            if not any(token in message for token in ("already", "exists", "409", "conflict")):
                logger.exception("Parcle user creation failed", extra={"user_id": self.user_id})
                raise ParcleError(f"Parcle user creation failed for {self.user_id}: {exc}") from exc
        self._user_checked = True

    def search(self, query: str, limit: int = 8) -> list[ParcleDocument]:
        self.ensure_user()
        try:
            result = self.client.search(user_id=self.user_id, query=query)
        except Exception as exc:
            logger.exception("Parcle search failed", extra={"user_id": self.user_id})
            raise ParcleError(f"Parcle search failed: {exc}") from exc
        document = self._normalize_search_result(result, query)
        return [document] if document.content else []

    def ingest_files(self, files: list[Path]) -> dict[str, Any]:
        if not files:
            raise ParcleError("At least one file is required for Parcle ingestion")
        self.ensure_user()
        responses = []
        for file_path in files:
            try:
                response = self.client.ingest_file(user_id=self.user_id, file=str(file_path))
            except Exception as exc:
                logger.exception("Parcle file ingestion failed", extra={"file": str(file_path)})
                raise ParcleError(f"Parcle file ingestion failed for {file_path}: {exc}") from exc
            responses.append(
                {
                    "file": str(file_path),
                    "response": self._to_jsonable(response),
                }
            )
        return {
            "location": self.memory_location,
            "user_id": self.user_id,
            "files_submitted": len(files),
            "responses": responses,
        }

    def ingest_documents(self, documents: list[ParcleMemoryDocument]) -> dict[str, Any]:
        """Store generated memory as Parcle dialog turns.

        The Parcle SDK does not expose document upsert; generated incident records are
        appended as dialog memory scoped to the configured system user.
        """
        if not documents:
            raise ParcleError("At least one document is required for Parcle ingestion")
        self.ensure_user()
        responses = []
        for document in documents:
            try:
                response = self.client.ingest_dialog(
                    user_id=self.user_id,
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                f"Store this incident memory from {document.reference}: "
                                f"{document.title}"
                            ),
                        },
                        {"role": "assistant", "content": document.content},
                    ],
                )
            except Exception as exc:
                logger.exception("Parcle dialog ingestion failed", extra={"document_id": document.id})
                raise ParcleError(f"Parcle dialog ingestion failed for {document.id}: {exc}") from exc
            responses.append(
                {
                    "id": document.id,
                    "reference": document.reference,
                    "response": self._to_jsonable(response),
                }
            )
        return {
            "location": self.memory_location,
            "user_id": self.user_id,
            "documents_submitted": len(documents),
            "responses": responses,
        }

    def upsert_documents(self, documents: list[ParcleMemoryDocument]) -> dict[str, Any]:
        return self.ingest_documents(documents)

    @classmethod
    def _normalize_search_result(cls, result: Any, query: str) -> ParcleDocument:
        answer = cls._field(result, "answer", "")
        confidence = cls._field(result, "confidence", None)
        citations = cls._field(result, "citations", [])
        citation_refs = cls._citation_references(citations)
        return ParcleDocument(
            title="Parcle memory answer",
            content=str(answer or ""),
            reference=", ".join(citation_refs) if citation_refs else None,
            metadata={
                "query": query,
                "confidence": confidence,
                "citations": cls._to_jsonable(citations),
            },
        )

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)

    @classmethod
    def _citation_references(cls, citations: Any) -> list[str]:
        if not isinstance(citations, list):
            return []
        references = []
        for citation in citations:
            citation_type = cls._field(citation, "type", "citation")
            citation_id = cls._field(citation, "id", None)
            references.append(f"{citation_type}:{citation_id}" if citation_id else str(citation_type))
        return references

    @classmethod
    def _to_jsonable(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [cls._to_jsonable(item) for item in value]
        if isinstance(value, tuple):
            return [cls._to_jsonable(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._to_jsonable(item) for key, item in value.items()}
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return cls._to_jsonable(model_dump(mode="json"))
        if hasattr(value, "__dict__"):
            return cls._to_jsonable(vars(value))
        return repr(value)
