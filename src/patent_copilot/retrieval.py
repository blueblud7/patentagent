from __future__ import annotations

import httpx

from patent_copilot.adapters.base import PartialPatentFetchError, PatentDataAdapter
from patent_copilot.core.patent_id import normalize_patent_id
from patent_copilot.core.schemas import PriorArtDocument, RetrievalAttempt


class PatentRetrievalError(ValueError):
    def __init__(self, ids: list[str], attempts: list[RetrievalAttempt]) -> None:
        self.ids = ids
        self.attempts = attempts
        missing = ", ".join(ids)
        super().__init__(
            "Could not fetch prior-art text for patent IDs: "
            f"{missing}. Pass prior_art_texts directly or verify the IDs."
        )


async def fetch_documents_from_providers(
    ids: list[str],
    providers: list[PatentDataAdapter],
) -> tuple[list[PriorArtDocument], list[RetrievalAttempt]]:
    normalized_ids = _unique_normalized_ids(ids)
    remaining_ids = list(normalized_ids)
    documents: list[PriorArtDocument] = []
    attempts: list[RetrievalAttempt] = []

    for provider in providers:
        if not remaining_ids:
            break

        provider_name = _provider_name(provider)
        try:
            fetched = await provider.fetch_documents(remaining_ids)
        except PartialPatentFetchError as exc:
            fetched = exc.documents
            for document in fetched:
                document.metadata.setdefault("source", provider_name)
            found_ids = {normalize_patent_id(document.id) for document in fetched}
            missing_ids = [patent_id for patent_id in remaining_ids if patent_id not in found_ids]
            attempts.append(
                RetrievalAttempt(
                    provider=provider_name,
                    requested_ids=list(remaining_ids),
                    found_ids=sorted(found_ids),
                    missing_ids=list(missing_ids),
                    status="partial",
                    error=str(exc),
                )
            )
            documents.extend(fetched)
            remaining_ids = missing_ids
            continue
        except (RuntimeError, httpx.HTTPError) as exc:
            attempts.append(
                RetrievalAttempt(
                    provider=provider_name,
                    requested_ids=list(remaining_ids),
                    missing_ids=list(remaining_ids),
                    status="error",
                    error=str(exc),
                )
            )
            continue

        for document in fetched:
            document.metadata.setdefault("source", provider_name)

        found_ids = {normalize_patent_id(document.id) for document in fetched}
        missing_ids = [patent_id for patent_id in remaining_ids if patent_id not in found_ids]
        attempts.append(
            RetrievalAttempt(
                provider=provider_name,
                requested_ids=list(remaining_ids),
                found_ids=sorted(found_ids),
                missing_ids=list(missing_ids),
                status="complete" if not missing_ids else "partial",
            )
        )
        documents.extend(fetched)
        remaining_ids = missing_ids

    ordered = order_documents(normalized_ids, documents)
    found_ids = {normalize_patent_id(document.id) for document in ordered}
    unresolved_ids = [patent_id for patent_id in normalized_ids if patent_id not in found_ids]
    if unresolved_ids:
        raise PatentRetrievalError(unresolved_ids, attempts)
    return ordered, attempts


def order_documents(ids: list[str], documents: list[PriorArtDocument]) -> list[PriorArtDocument]:
    by_id = {normalize_patent_id(document.id): document for document in documents}
    ordered = []
    for patent_id in ids:
        document = by_id.get(normalize_patent_id(patent_id))
        if document is not None:
            ordered.append(document)
    return ordered


def _unique_normalized_ids(ids: list[str]) -> list[str]:
    output = []
    seen = set()
    for item in ids:
        normalized = normalize_patent_id(item)
        if normalized in seen:
            continue
        output.append(normalized)
        seen.add(normalized)
    return output


def _provider_name(provider: PatentDataAdapter) -> str:
    name = provider.__class__.__name__
    if name == "PatentsViewAdapter":
        return "patentsview"
    name = name.removesuffix("Adapter")
    return _snake_case(name)


def _snake_case(value: str) -> str:
    output = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            output.append("_")
        output.append(char.lower())
    return "".join(output)
