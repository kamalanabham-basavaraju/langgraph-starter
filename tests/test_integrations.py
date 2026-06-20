from app.integrations.parcel.client import ParcelClient


def test_parcel_normalizes_common_response_fields():
    document = ParcelClient._normalize(
        {"name": "Runbook", "snippet": "Restart the worker", "url": "docs/runbook", "metadata": {"team": "ops"}}
    )
    assert document.title == "Runbook"
    assert document.content == "Restart the worker"
    assert document.reference == "docs/runbook"
    assert document.metadata == {"team": "ops"}
