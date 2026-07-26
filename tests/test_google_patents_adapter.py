from pathlib import Path

import pytest

from patent_copilot.adapters.base import PartialPatentFetchError
from patent_copilot.adapters.google_patents import GooglePatentsAdapter, parse_google_patents_html


def test_parse_google_patents_html_sections() -> None:
    html = Path("examples/google_patents_sample.html").read_text()

    document = parse_google_patents_html(html, "US-DEMO-HTML")

    assert document.id == "USDEMOHTML"
    assert document.title == "Sensor classification system"
    assert "processor receives sensor data" in (document.description or "").lower()
    assert "system including a processor" in (document.claims or "").lower()


def test_google_patents_fetch_documents_reports_partial_success() -> None:
    html = Path("examples/google_patents_sample.html").read_text()

    class MixedGooglePatentsAdapter(GooglePatentsAdapter):
        async def _fetch_html(self, url: str) -> str:
            if "US2222222B2" in url:
                raise RuntimeError("not found")
            return html

    with pytest.raises(PartialPatentFetchError) as exc_info:
        import asyncio

        asyncio.run(
            MixedGooglePatentsAdapter().fetch_documents(
                ["US1111111B2", "US2222222B2"],
            )
        )

    assert [document.id for document in exc_info.value.documents] == ["US1111111B2"]
    assert "US2222222B2" in exc_info.value.errors
