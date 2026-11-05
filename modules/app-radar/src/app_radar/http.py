from __future__ import annotations

import time
from typing import Any, Callable

import requests

# Wikimedia counts a User-Agent without contact info as unidentified (10 requests a minute).
USER_AGENT = "app-radar/0.1 (+https://github.com/yujiachen-y/daily-build-newsletter)"
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER = 120


class FetchError(RuntimeError):
    pass


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    retries: int = 2,
    backoff: float = 3.0,
    timeout: int = 30,
    sleep: Callable[[float], None] = time.sleep,
    missing_ok: bool = False,
    **kwargs: Any,
) -> Any:
    """Send a request and decode JSON, retrying transient failures.

    With missing_ok, a 404 returns None instead of raising (e.g. a Wikipedia article that
    does not exist).
    """
    last_error = ""
    for attempt in range(retries + 1):
        wait = backoff * (attempt + 1)
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError as exc:
                    raise FetchError(f"invalid JSON from {url}") from exc
            if response.status_code == 404 and missing_ok:
                return None
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            if response.status_code not in RETRY_STATUS:
                break
            wait = _retry_after(response) or wait
        if attempt < retries:
            sleep(wait)
    raise FetchError(f"{method} {url} failed: {last_error}")


def _retry_after(response: Any) -> float | None:
    value = (getattr(response, "headers", None) or {}).get("Retry-After")
    try:
        return min(float(value), MAX_RETRY_AFTER) if value else None
    except ValueError:  # an HTTP date instead of seconds
        return None
