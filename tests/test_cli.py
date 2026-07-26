import json

from patent_copilot.cli import main


def test_demo_cli_rejects_missing_claim_text(tmp_path, capsys) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "prior_art_texts": [
                    {
                        "id": "US-DEMO-1",
                        "description": "A processor receives sensor data.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    try:
        main([str(request_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("missing claim_text should fail argument parsing")

    assert "request must include non-empty claim_text" in capsys.readouterr().err


def test_demo_cli_rejects_invalid_json_without_traceback(tmp_path, capsys) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text("{", encoding="utf-8")

    try:
        main([str(request_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("invalid JSON should fail argument parsing")

    err = capsys.readouterr().err
    assert "request must be valid JSON" in err
    assert "Traceback" not in err


def test_demo_cli_rejects_non_object_json(tmp_path, capsys) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text("[]", encoding="utf-8")

    try:
        main([str(request_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("non-object JSON should fail argument parsing")

    assert "request JSON must be an object" in capsys.readouterr().err


def test_demo_cli_rejects_invalid_prior_art_texts(tmp_path, capsys) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "claim_text": "1. A system comprising: a processor.",
                "prior_art_texts": [{"id": "US-DEMO-1"}],
            }
        ),
        encoding="utf-8",
    )

    try:
        main([str(request_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("manual document without text should fail argument parsing")

    assert "at least one text field" in capsys.readouterr().err


def test_demo_cli_rejects_too_many_prior_art_texts(tmp_path, capsys) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "claim_text": "1. A system comprising: a processor.",
                "prior_art_texts": [
                    {"id": f"US-DEMO-{index}", "description": "A processor receives data."}
                    for index in range(26)
                ],
            }
        ),
        encoding="utf-8",
    )

    try:
        main([str(request_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("too many manual documents should fail argument parsing")

    assert "at most 25 prior-art references" in capsys.readouterr().err


def test_demo_cli_explains_prior_art_ids_are_not_fetched_offline(tmp_path, capsys) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "claim_text": "1. A system comprising: a processor.",
                "prior_art_ids": ["US12345678B2"],
            }
        ),
        encoding="utf-8",
    )

    try:
        main([str(request_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("ID-only offline request should fail argument parsing")

    err = capsys.readouterr().err
    assert "offline demo does not fetch prior_art_ids" in err
    assert "Provide prior_art_texts" in err
    assert "MCP build_claim_chart tool" in err


def test_demo_cli_outputs_json_for_valid_request(tmp_path, capsys) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "claim_text": "1. A system comprising: a processor receiving sensor data.",
                "prior_art_texts": [
                    {
                        "id": "US-DEMO-1",
                        "description": "A processor receives sensor data.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main([str(request_path), "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["claim_text"].startswith("1. A system")
    assert payload["rows"]


def test_demo_cli_outputs_summary_for_valid_request(tmp_path, capsys) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "claim_text": "1. A system comprising: a processor receiving sensor data.",
                "prior_art_texts": [
                    {
                        "id": "US-DEMO-1",
                        "description": "A processor receives sensor data.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main([str(request_path), "--format", "summary"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["claim_text"].startswith("1. A system")
    assert payload["review_summary"]["total_rows"] > 0
    assert "rows" not in payload
    assert "review_flag_counts" in payload["review_summary"]


def test_demo_cli_writes_formatted_output_file(tmp_path, capsys) -> None:
    request_path = tmp_path / "request.json"
    output_path = tmp_path / "artifacts" / "chart.csv"
    request_path.write_text(
        json.dumps(
            {
                "claim_text": "1. A system comprising: a processor receiving sensor data.",
                "prior_art_texts": [
                    {
                        "id": "US-DEMO-1",
                        "description": "A processor receives sensor data.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main([str(request_path), "--format", "csv", "--output", str(output_path)]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"wrote {output_path}" in captured.err
    assert output_path.read_text(encoding="utf-8").startswith(
        "element_no,role,claim_element,best_prior_art_id"
    )
