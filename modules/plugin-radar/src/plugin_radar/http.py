from __future__ import annotations

import time
from typing import Any, Callable

import requests

# skills.sh and SkillHub serve their pages to browsers; a bare client UA gets the same HTML.
USER_AGENT = "plugin-radar/0.1 (+https://github.com/yujiachen-y/daily-build-newsletter)"
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER = 120


class FetchError(RuntimeError):
    pass


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def request(
    session: requests.Session,
    method: str,
    url: str,
    *,
    retries: int = 2,
    backoff: float = 3.0,
    timeout: int = 60,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs: Any,
) -> requests.Response:
    """Send a request, retrying network errors and 429/5xx. Raises FetchError otherwise."""
    last_error = ""
    for attempt in range(retries + 1):
        wait = backoff * (attempt + 1)
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code < 400:
                return response
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            if response.status_code not in RETRY_STATUS:
                break
            wait = _retry_after(response) or wait
        if attempt < retries:
            sleep(wait)
    raise FetchError(f"{method} {url} failed: {last_error}")


def get_text(session: requests.Session, url: str, **kwargs: Any) -> str:
    return request(session, "GET", url, **kwargs).text


def get_json(session: requests.Session, url: str, **kwargs: Any) -> Any:
    response = request(session, "GET", url, **kwargs)
    try:
        return response.json()
    except ValueError as exc:
        raise FetchError(f"invalid JSON from {url}") from exc


def _retry_after(response: Any) -> float | None:
    value = (getattr(response, "headers", None) or {}).get("Retry-After")
    try:
        return min(float(value), MAX_RETRY_AFTER) if value else None
    except ValueError:  # an HTTP date instead of seconds
        return None
