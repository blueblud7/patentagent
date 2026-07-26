import json

from patent_copilot import release_check_cli
from scripts import write_release_manifest


def test_write_release_manifest_records_ci_steps_without_secret(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "release_manifest.json"
    monkeypatch.setattr(release_check_cli, "RELEASE_MANIFEST_PATH", str(output_path))
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key")

    assert write_release_manifest.main(["--require-live", "--patent-id", "US12000000B2"]) == 0

    text = output_path.read_text(encoding="utf-8")
    manifest = json.loads(text)
    assert manifest["schema_version"] == "1.0"
    assert manifest["success"] is True
    assert manifest["require_live"] is True
    assert manifest["api_key_configured"] is True
    assert manifest["patent_id"] == "US12000000B2"
    assert "test-key" not in text
    assert [step["name"] for step in manifest["steps"]][-1] == "strict_live_retrieval_smoke"
    assert all(step["return_code"] == 0 for step in manifest["steps"])
    assert all(step["passed"] is True for step in manifest["steps"])


def test_write_release_manifest_rejects_blank_patent_id(monkeypatch, tmp_path, capsys) -> None:
    output_path = tmp_path / "release_manifest.json"
    monkeypatch.setattr(release_check_cli, "RELEASE_MANIFEST_PATH", str(output_path))

    try:
        write_release_manifest.main(["--patent-id", "   "])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("blank patent ID should fail argument parsing")

    assert "--patent-id must not be blank" in capsys.readouterr().err
    assert not output_path.exists()
