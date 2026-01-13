from __future__ import annotations

from typing import Any

import requests

USER_AGENT = "article-harvest/0.1 (+local)"


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def get_text(session: requests.Session, url: str, timeout: int = 20) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def get_bytes(session: requests.Session, url: str, timeout: int = 20) -> bytes:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def get_json(session: requests.Session, url: str, timeout: int = 20) -> Any:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()
