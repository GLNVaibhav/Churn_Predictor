from __future__ import annotations

from backend.mappers.platform_enricher import enrich_platform_payload
from backend.models.execution_result import ExecutionMetadata, ExecutionResult


class ResponseStub:
    def to_dict(self):
        return {"dataset": {"filename": r"C:\private\uploads\customer.csv", "sector": "telecom"}}


def test_platform_payload_exposes_dataset_name_without_server_path():
    execution = ExecutionResult(metadata=ExecutionMetadata(
        sector="telecom",
        mode="auto",
        input_path=r"C:\private\uploads\customer.csv",
    ))

    payload = enrich_platform_payload(ResponseStub(), execution)

    assert payload["dataset"]["filename"] == "customer.csv"
    assert payload["filename"] == "customer.csv"
    assert "C:\\private" not in payload["cli_output"]["text"]
    assert payload["execution_result"]["metadata"]["input_path"] == "customer.csv"
    assert payload["execution_state"]["input_path"] == "customer.csv"
