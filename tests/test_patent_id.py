from patent_copilot.core.patent_id import (
    google_patents_url,
    is_us_publication_id,
    normalize_patent_id,
    patentsview_numeric_id,
)


def test_normalize_patent_id_common_forms() -> None:
    assert normalize_patent_id("us 12,345,678 b2") == "US12345678B2"
    assert normalize_patent_id("12345678") == "US12345678"
    assert (
        normalize_patent_id("https://patents.google.com/patent/US12345678B2/en")
        == "US12345678B2"
    )


def test_patent_id_urls_and_patentsview_ids() -> None:
    assert google_patents_url("US12345678B2") == "https://patents.google.com/patent/US12345678B2/en"
    assert patentsview_numeric_id("US12345678B2") == "12345678"
    assert patentsview_numeric_id("US20240370584A1") == "20240370584"
    assert is_us_publication_id("US20240370584A1")
    assert not is_us_publication_id("US12345678B2")
