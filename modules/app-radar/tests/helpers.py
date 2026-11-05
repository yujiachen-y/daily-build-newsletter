from __future__ import annotations

from typing import Any


class DummyResponse:
    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no json")
        return self._json


class DummySession:
    """Routes requests by a predicate over (method, url, kwargs); records every call."""

    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[tuple[str, str, dict]] = []
        self.headers: dict[str, str] = {}

    def request(self, method: str, url: str, **kwargs: Any) -> DummyResponse:
        self.calls.append((method, url, kwargs))
        return self.handler(method, url, kwargs)


def rss_entry(app_id: str, name: str, artist: str, release: str) -> dict[str, Any]:
    return {
        "id": {
            "label": f"https://apps.apple.com/app/id{app_id}",
            "attributes": {"im:id": app_id, "im:bundleId": f"com.example.{app_id}"},
        },
        "im:name": {"label": name},
        "im:artist": {"label": artist},
        "im:releaseDate": {"label": f"{release}T00:00:00-07:00"},
    }


def chart_row(
    country: str,
    genre: str,
    chart: str,
    rank: int,
    app_id: str,
    name: str,
    artist: str,
    release: str,
) -> dict[str, Any]:
    return {
        "country": country,
        "genre": genre,
        "chart": chart,
        "rank": rank,
        "app_id": app_id,
        "bundle_id": None,
        "name": name,
        "artist": artist,
        "release_date": release,
        "url": None,
    }


def lookup_row(country: str, app_id: str, name: str, ratings: int, release: str) -> dict[str, Any]:
    return {
        "country": country,
        "app_id": app_id,
        "name": name,
        "seller": "s",
        "ratings": ratings,
        "rating_avg": 4.5,
        "release_date": release,
        "version_date": release,
        "price": 0.0,
        "currency": "USD",
        "genre": "Health",
        "languages": ["EN"],
        "url": f"https://apps.apple.com/app/id{app_id}",
        "description_head": "desc",
    }
