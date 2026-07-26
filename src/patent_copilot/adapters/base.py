from __future__ import annotations

from abc import ABC, abstractmethod

from patent_copilot.core.schemas import PriorArtDocument, PriorArtSearchResult


class PartialPatentFetchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        documents: list[PriorArtDocument],
        errors: dict[str, str],
    ) -> None:
        self.documents = documents
        self.errors = errors
        super().__init__(message)


class PatentDataAdapter(ABC):
    @abstractmethod
    async def search_prior_art(
        self,
        query: str,
        *,
        jurisdiction: str | None = None,
        date_before: str | None = None,
        limit: int = 10,
    ) -> list[PriorArtSearchResult]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_documents(self, ids: list[str]) -> list[PriorArtDocument]:
        raise NotImplementedError
