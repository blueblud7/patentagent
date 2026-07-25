from pathlib import Path

from patent_copilot.adapters.google_patents import parse_google_patents_html


def test_parse_google_patents_html_sections() -> None:
    html = Path("examples/google_patents_sample.html").read_text()

    document = parse_google_patents_html(html, "US-DEMO-HTML")

    assert document.id == "USDEMOHTML"
    assert document.title == "Sensor classification system"
    assert "processor receives sensor data" in (document.description or "").lower()
    assert "system including a processor" in (document.claims or "").lower()

