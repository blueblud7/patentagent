from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any


class MappingStatus(str, Enum):
    DISCLOSED = "Disclosed"
    PARTIALLY_DISCLOSED = "Partially disclosed"
    NOT_FOUND = "Not found"
    AMBIGUOUS = "Ambiguous"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ElementRole(str, Enum):
    PREAMBLE = "preamble"
    STRUCTURAL = "structural"
    FUNCTIONAL = "functional"
    RELATIONSHIP = "relationship"
    RESULT = "result"
    UNKNOWN = "unknown"


class ModelMixin:
    @classmethod
    def model_validate(cls, value: Any):
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls(**value)
        raise TypeError(f"Cannot validate {type(value)!r} as {cls.__name__}")

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass
class PriorArtDocument(ModelMixin):
    id: str
    title: str | None = None
    abstract: str | None = None
    claims: str | None = None
    description: str | None = None
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def searchable_sections(self) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        for name in ("title", "abstract", "claims", "description"):
            value = getattr(self, name)
            if value:
                sections.append((name.title(), value))
        return sections


@dataclass
class ClaimElement(ModelMixin):
    element_no: str
    text: str
    role: ElementRole = ElementRole.UNKNOWN
    signals: list[str] = field(default_factory=list)


@dataclass
class Evidence(ModelMixin):
    prior_art_id: str
    section: str
    quote: str
    score: float
    why_relevant: str
    locator: str | None = None


@dataclass
class ClaimChartRow(ModelMixin):
    element_no: str
    claim_element: str
    prior_art_id: str | None
    mapping: MappingStatus
    analysis: str
    confidence: Confidence
    role: ElementRole = ElementRole.UNKNOWN
    evidence: list[Evidence] = field(default_factory=list)
    reference_mappings: list["ReferenceMapping"] = field(default_factory=list)
    gap: str | None = None


@dataclass
class ReferenceMapping(ModelMixin):
    prior_art_id: str
    mapping: MappingStatus
    confidence: Confidence
    evidence: list[Evidence] = field(default_factory=list)
    analysis: str = ""
    gap: str | None = None


@dataclass
class ClaimChart(ModelMixin):
    claim_text: str
    elements: list[ClaimElement]
    rows: list[ClaimChartRow]
    markdown: str
    csv: str = ""
    disclaimer: str = (
        "Research and drafting assistance only. Not legal advice. "
        "Review by a qualified patent professional is required."
    )


@dataclass
class PriorArtSearchResult(ModelMixin):
    id: str
    reason: str
    title: str | None = None
    abstract: str | None = None
    publication_date: str | None = None
    jurisdiction: str | None = None
    url: str | None = None
    score: float | None = None


def _json_ready(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
