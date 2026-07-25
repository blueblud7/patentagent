from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from patent_copilot.core.prompts import build_mapping_prompt
from patent_copilot.core.schemas import ClaimElement, Evidence, PriorArtDocument, ReferenceMapping


@dataclass
class ReferenceMappingPrompt:
    prior_art_id: str
    prompt: str


class MappingModel(Protocol):
    async def map_element(
        self,
        element: ClaimElement,
        document: PriorArtDocument,
        evidence: list[Evidence],
    ) -> ReferenceMapping | ReferenceMappingPrompt:
        raise NotImplementedError


@dataclass
class PromptOnlyMappingModel:
    """LLM integration boundary that returns the prompt for external execution.

    This keeps the core deterministic while making the intended LLM handoff explicit.
    A future OpenAI/Anthropic/local model adapter can implement MappingModel and parse
    model JSON into ReferenceMapping.
    """

    async def map_element(
        self,
        element: ClaimElement,
        document: PriorArtDocument,
        evidence: list[Evidence],
    ) -> ReferenceMappingPrompt:
        return ReferenceMappingPrompt(
            prior_art_id=document.id,
            prompt=build_mapping_prompt(element, document, evidence),
        )
