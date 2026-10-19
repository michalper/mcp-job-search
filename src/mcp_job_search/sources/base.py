"""Shared shapes every job source returns, so `search.py` can merge them uniformly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class NormalizedJob:
    title: str
    company: str | None
    location: str | None
    salary: str | None
    url: str
    source: str
    posted_date: str | None
    remote: bool | None


@dataclass(frozen=True)
class SourceError:
    source: str
    reason: str


class JobSource(Protocol):
    """A searchable job source. `name` is stable and used in `NormalizedJob.source`."""

    name: str

    def available(self) -> bool:
        """False when required credentials aren't set — search.py skips it, never calls it."""
        ...

    def search(
        self, keywords: str, location: str | None, remote_only: bool
    ) -> tuple[list[NormalizedJob], SourceError | None]:
        """Never raises: network/parse failures come back as a populated SourceError."""
        ...
