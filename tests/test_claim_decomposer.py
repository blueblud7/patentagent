from patent_copilot.core.claim_decomposer import decompose_claim


def test_decompose_claim_keeps_reviewable_elements() -> None:
    claim = (
        "1. A system comprising: a processor configured to receive sensor data; "
        "and a memory storing instructions to classify the sensor data."
    )

    elements = decompose_claim(claim)

    assert [element.element_no for element in elements] == ["1A", "1B", "1C"]
    assert elements[0].text == "A system comprising"
    assert "processor" in elements[1].text
    assert "memory" in elements[2].text

