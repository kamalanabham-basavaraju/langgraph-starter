from pathlib import Path
from types import SimpleNamespace

from app.integrations.parcle.client import ParcleClient
from app.models.incident import ParcleMemoryDocument


class RecordingParcleSdk:
    def __init__(self):
        self.users = []
        self.files = []
        self.dialogs = []

    def create_user(self, user_id):
        self.users.append(user_id)

    def ingest_file(self, user_id, file):
        self.files.append((user_id, file))
        return {"file_id": Path(file).name}

    def ingest_dialog(self, user_id, messages):
        self.dialogs.append((user_id, messages))
        return SimpleNamespace(session_id="session-1")

    def search(self, user_id, query):
        return SimpleNamespace(
            answer="Restart the worker",
            confidence=0.91,
            citations=[SimpleNamespace(type="file", id="README.md")],
        )


def test_parcle_search_uses_system_user_and_normalizes_sdk_result():
    sdk = RecordingParcleSdk()
    client = ParcleClient(api_key="secret", user_id="system_user", sdk_client=sdk)

    documents = client.search("worker down")

    assert sdk.users == ["system_user"]
    assert documents[0].title == "Parcle memory answer"
    assert documents[0].content == "Restart the worker"
    assert documents[0].reference == "file:README.md"
    assert documents[0].metadata["confidence"] == 0.91


def test_parcle_ingests_files_with_configured_user(tmp_path):
    sdk = RecordingParcleSdk()
    client = ParcleClient(api_key="secret", user_id="system_user", sdk_client=sdk)
    readme = tmp_path / "README.md"
    readme.write_text("docs", encoding="utf-8")

    result = client.ingest_files([readme])

    assert sdk.files == [("system_user", str(readme))]
    assert result["location"] == "parcle-sdk user:system_user"
    assert result["files_submitted"] == 1


def test_parcle_stores_generated_documents_as_dialog_memory():
    sdk = RecordingParcleSdk()
    client = ParcleClient(api_key="secret", user_id="system_user", sdk_client=sdk)

    result = client.ingest_documents([
        ParcleMemoryDocument(id="doc:1", title="Decision", content="Fixed validation", reference="docs/log.md")
    ])

    assert result["documents_submitted"] == 1
    assert sdk.dialogs[0][0] == "system_user"
    assert sdk.dialogs[0][1][1]["content"] == "Fixed validation"
