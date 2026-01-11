from __future__ import annotations

from article_ingest.ingest_fetch import DEFAULT_USER_AGENT, build_session


def test_build_session_default_user_agent() -> None:
    session = build_session(None)
    assert session.headers["User-Agent"] == DEFAULT_USER_AGENT


def test_build_session_custom_user_agent() -> None:
    custom = "CustomUA/1.0"
    session = build_session(custom)
    assert session.headers["User-Agent"] == custom
