from pathlib import Path

import pytest

from app.services.parcle_ingestion import EMPLOYEE_PORTAL_MEMORY_FILES, ParcleIngestionService


class RecordingParcle:
    memory_location = "parcle-sdk user:system_user"

    def __init__(self):
        self.files = []

    def ingest_files(self, files):
        self.files = files
        return {"location": self.memory_location, "files_submitted": len(files)}


def test_ingests_exact_employee_portal_memory_files(tmp_path: Path):
    for name in EMPLOYEE_PORTAL_MEMORY_FILES:
        (tmp_path / name).write_text(f"# {name}\ncontent", encoding="utf-8")
    parcle = RecordingParcle()

    result = ParcleIngestionService(parcle, tmp_path).ingest()  # type: ignore[arg-type]

    assert result["files_submitted"] == 3
    assert [path.name for path in parcle.files] == list(EMPLOYEE_PORTAL_MEMORY_FILES)
    assert list(result["checksums"]) == list(EMPLOYEE_PORTAL_MEMORY_FILES)
    assert len(result["checksums"]["API_DOCUMENTATION.md"]) == 64


def test_ingestion_reports_all_missing_required_files(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="API_DOCUMENTATION.md.*PARCLE_MEMORY.md.*README.md"):
        ParcleIngestionService(RecordingParcle(), tmp_path).load_documents()  # type: ignore[arg-type]


def test_dry_run_does_not_write_to_parcle(tmp_path: Path):
    for name in EMPLOYEE_PORTAL_MEMORY_FILES:
        (tmp_path / name).write_text("content", encoding="utf-8")
    parcle = RecordingParcle()

    result = ParcleIngestionService(parcle, tmp_path).ingest(dry_run=True)  # type: ignore[arg-type]

    assert result["dry_run"] is True
    assert result["documents_submitted"] == 0
    assert parcle.files == []
