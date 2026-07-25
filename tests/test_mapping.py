import asyncio

from patent_copilot.core.claim_decomposer import decompose_claim
from patent_copilot.core.mapping import PromptOnlyMappingModel
from patent_copilot.core.schemas import Evidence, PriorArtDocument


def test_prompt_only_mapping_model_builds_review_prompt() -> None:
    element = decompose_claim(
        "1. A system comprising: a processor configured to receive sensor data."
    )[1]
    document = PriorArtDocument(id="US-DEMO", title="Sensor system")
    evidence = [
        Evidence(
            prior_art_id="US-DEMO",
            section="Description",
            quote="The processor receives sensor data.",
            score=0.9,
            why_relevant="Shares material terms.",
            locator="0001",
        )
    ]

    result = asyncio.run(PromptOnlyMappingModel().map_element(element, document, evidence))

    assert result.prior_art_id == "US-DEMO"
    assert "Claim element:" in result.prompt
    assert "The processor receives sensor data." in result.prompt

