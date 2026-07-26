from __future__ import annotations

import json

from patent_copilot import live_retrieval_cli
from patent_copilot.core.schemas import PriorArtDocument
from patent_copilot.live_retrieval_cli import main


def test_live_retrieval_smoke_skips_without_api_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)

    exit_code = main([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"skipped": true' in output
    assert '"api_key_configured": false' in output
    assert '"patent_id": "US12000000B2"' in output
    assert "recent grant years" in output
    assert "PATENTSVIEW_API_KEY is not configured" in output


def test_live_retrieval_smoke_can_require_api_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)

    exit_code = main(["--require-api-key"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["skipped"] is True
    assert output["require_api_key"] is True
    assert output["api_key_configured"] is False
    assert "PATENTSVIEW_API_KEY is not configured" in output["message"]


def test_live_retrieval_smoke_writes_output_file_when_skipped(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)
    output_path = tmp_path / "reports" / "live.json"

    assert main(["--output", str(output_path)]) == 0

    stdout_output = json.loads(capsys.readouterr().out)
    file_output = json.loads(output_path.read_text(encoding="utf-8"))
    assert file_output == stdout_output
    assert file_output["skipped"] is True
    assert file_output["api_key_configured"] is False


def test_live_retrieval_smoke_treats_blank_api_key_as_missing(monkeypatch, capsys) -> None:
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "   ")

    exit_code = main(["--require-api-key"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["skipped"] is True
    assert output["api_key_configured"] is False
    assert "PATENTSVIEW_API_KEY is not configured" in output["message"]


def test_live_retrieval_smoke_passes_with_claims_and_description(monkeypatch, capsys) -> None:
    class FakePatentsViewAdapter:
        async def fetch_documents(self, ids: list[str]) -> list[PriorArtDocument]:
            return [
                PriorArtDocument(
                    id=ids[0],
                    claims="1. A processor configured to receive sensor data.",
                    description="The processor receives sensor data from an input interface.",
                    url="https://patents.google.com/patent/US12000000B2/en",
                    metadata={"text_sources": ["patent", "g_claim", "g_detail_desc_text"]},
                )
            ]

    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")
    monkeypatch.setattr(live_retrieval_cli, "PatentsViewAdapter", FakePatentsViewAdapter)

    assert main(["--require-api-key"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["documents_fetched"] == 1
    assert output["api_key_configured"] is True
    assert output["fetched_document_id"] == "US12000000B2"
    assert output["document_url"] == "https://patents.google.com/patent/US12000000B2/en"
    assert output["record_type"] == "grant"
    assert output["elapsed_seconds"] >= 0
    assert output["has_claims"] is True
    assert output["has_description"] is True
    assert output["message"] == "live PatentsView retrieval smoke passed"


def test_live_retrieval_smoke_accepts_patent_id_argument(monkeypatch, capsys) -> None:
    class FakePatentsViewAdapter:
        async def fetch_documents(self, ids: list[str]) -> list[PriorArtDocument]:
            return [
                PriorArtDocument(
                    id=ids[0],
                    claims="1. A controller comprising a processor.",
                    description="The controller uses the processor to operate the device.",
                    metadata={"text_sources": ["publication", "pg_claim", "pg_brf_sum_text"]},
                )
            ]

    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")
    monkeypatch.setenv("PATENT_COPILOT_LIVE_PATENT_ID", "US12000000B2")
    monkeypatch.setattr(live_retrieval_cli, "PatentsViewAdapter", FakePatentsViewAdapter)

    assert main(["--require-api-key", "--patent-id", "US20240000001A1"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["patent_id"] == "US20240000001A1"
    assert output["fetched_document_id"] == "US20240000001A1"


def test_live_retrieval_smoke_rejects_blank_patent_id_argument(capsys) -> None:
    try:
        main(["--patent-id", "   "])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("blank --patent-id should fail argument parsing")

    assert "--patent-id must not be blank" in capsys.readouterr().err


def test_live_retrieval_smoke_fails_without_claims(monkeypatch, capsys) -> None:
    class FakePatentsViewAdapter:
        async def fetch_documents(self, ids: list[str]) -> list[PriorArtDocument]:
            return [
                PriorArtDocument(
                    id=ids[0],
                    description="The processor receives sensor data from an input interface.",
                    metadata={"text_sources": ["patent", "g_detail_desc_text"]},
                )
            ]

    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")
    monkeypatch.setattr(live_retrieval_cli, "PatentsViewAdapter", FakePatentsViewAdapter)

    assert main(["--require-api-key"]) == 1

    output = json.loads(capsys.readouterr().out)
    assert output["has_claims"] is False
    assert "did not return claims text" in output["message"]
