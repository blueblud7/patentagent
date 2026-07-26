from pathlib import Path

from patent_copilot.preflight_cli import MIN_RUNTIME, build_preflight_status


def test_preflight_runtime_floor() -> None:
    assert MIN_RUNTIME == (3, 11)


def test_preflight_does_not_import_live_retrieval_dependencies() -> None:
    source = Path("src/patent_copilot/preflight_cli.py").read_text(encoding="utf-8")

    assert "live_retrieval_cli" not in source
    assert "import httpx" not in source


def test_preflight_reports_live_validation_next_step_without_key(monkeypatch) -> None:
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)

    status = build_preflight_status()

    assert status["dependencies"]["pydantic_installed"] is True
    assert status["capabilities"]["mcp_server_runtime"] is True
    assert status["capabilities"]["patentsview_api_key_configured"] is False
    assert status["live_validation"]["api_key_configured"] is False
    assert status["live_validation"]["patent_id"] == "US12000000B2"
    assert "--patent-id US12000000B2" in status["live_validation"]["strict_command"]
    assert any("patent-copilot-release-check --require-live" in item for item in status["next_steps"])


def test_preflight_treats_blank_api_key_as_missing(monkeypatch) -> None:
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "   ")

    status = build_preflight_status()

    assert status["capabilities"]["patentsview_api_key_configured"] is False
    assert status["next_steps"]


def test_preflight_omits_key_next_step_when_key_is_configured(monkeypatch) -> None:
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")

    status = build_preflight_status()

    assert status["capabilities"]["patentsview_api_key_configured"] is True
    assert status["live_validation"]["api_key_configured"] is True
    assert status["next_steps"] == []


def test_preflight_reports_live_patent_id_override(monkeypatch) -> None:
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")
    monkeypatch.setenv("PATENT_COPILOT_LIVE_PATENT_ID", "US20240000001A1")

    status = build_preflight_status()

    assert status["live_validation"]["patent_id_env"] == "PATENT_COPILOT_LIVE_PATENT_ID"
    assert status["live_validation"]["patent_id"] == "US20240000001A1"
    assert "--patent-id US20240000001A1" in status["live_validation"]["strict_command"]
