from __future__ import annotations

import pytest
from helpers import DummyResponse, DummySession

from app_radar.http import FetchError, request_json


def test_retry_after_header_sets_the_wait():
    responses = iter(
        [
            DummyResponse(429, text="slow down", headers={"Retry-After": "7"}),
            DummyResponse(json_data={"ok": True}),
        ]
    )
    waits = []
    session = DummySession(lambda m, u, k: next(responses))
    assert request_json(session, "GET", "https://x", sleep=waits.append) == {"ok": True}
    assert waits == [7.0]


def test_missing_ok_turns_404_into_none():
    session = DummySession(lambda m, u, k: DummyResponse(404, text="nope"))
    assert request_json(session, "GET", "https://x", missing_ok=True) is None
    with pytest.raises(FetchError):
        request_json(session, "GET", "https://x", sleep=lambda s: None)
