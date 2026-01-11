from __future__ import annotations

from typing import Protocol

import requests

from ..models import ItemCandidate, Source


class AdapterError(Exception):
    pass


class SourceAdapter(Protocol):
    def discover(self, source: Source, session: requests.Session) -> list[ItemCandidate]:
        ...

    def fetch_detail(self, candidate: ItemCandidate, session: requests.Session) -> str:
        ...
