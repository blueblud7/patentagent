from __future__ import annotations

from patent_copilot.core.schemas import ClaimElement, Evidence, PriorArtDocument

CLAIM_DECOMPOSITION_PROMPT = """\
You are assisting a patent professional with claim-chart preparation.

Task:
Decompose the claim into chartable elements. Keep legally meaningful limitations together.
Do not rewrite claim language except to remove numbering or punctuation artifacts.

Rules:
- Preserve antecedent-basis relationships.
- Separate preamble, structural limitations, functional limitations, relationship limitations, and result limitations when appropriate.
- Do not create an element that cannot be mapped to evidence independently.
- Return JSON with element_no, text, role, and signals.
"""


EVIDENCE_MAPPING_PROMPT = """\
You are assisting a patent professional with an evidence-grounded claim chart.

Task:
Map one claim element to prior-art passages.

Rules:
- A limitation is Disclosed only when cited text supports every material part of the element.
- If a passage supports only part of the element, mark Partially disclosed and identify the gap.
- If no cited text supports the element, mark Not found.
- Do not infer missing structure or functionality from broad field-of-use language.
- Quote only the minimum passage needed for review.
- This is research assistance, not legal advice.
"""


def build_mapping_prompt(
    element: ClaimElement,
    document: PriorArtDocument,
    evidence: list[Evidence],
) -> str:
    passages = "\n".join(
        f"- {item.section} {f'[{item.locator}]' if item.locator else ''}: {item.quote}"
        for item in evidence
    )
    if not passages:
        passages = "- No candidate passages were retrieved."

    return f"""{EVIDENCE_MAPPING_PROMPT}

Claim element:
{element.element_no} ({element.role.value}): {element.text}

Prior-art reference:
{document.id} {document.title or ""}

Candidate passages:
{passages}

Return JSON:
{{
  "prior_art_id": "{document.id}",
  "mapping": "Disclosed | Partially disclosed | Ambiguous | Not found",
  "confidence": "high | medium | low",
  "evidence": [
    {{"section": "...", "locator": "...", "quote": "...", "why_relevant": "..."}}
  ],
  "analysis": "...",
  "gap": "..."
}}
"""
