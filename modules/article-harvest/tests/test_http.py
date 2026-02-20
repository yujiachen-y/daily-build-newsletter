from __future__ import annotations

from article_harvest.http import create_session, get_bytes, get_json, get_text


class _DummyResponse:
    def __init__(self, *, text="", content=b"", json_data=None):
        self.text = text
        self.content = content
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class _DummySession:
    def __init__(self, response):
        self.response = response
        self.last_url = None
        self.last_kwargs = {}

    def get(self, url, **kwargs):
        self.last_url = url
        self.last_kwargs = kwargs
        return self.response


def test_create_session_sets_user_agent():
    session = create_session()
    assert "article-harvest" in session.headers.get("User-Agent", "")


def test_get_text():
    resp = _DummyResponse(text="hello world")
    session = _DummySession(resp)
    result = get_text(session, "https://example.com")
    assert result == "hello world"
    assert session.last_url == "https://example.com"
    assert session.last_kwargs.get("timeout") == 20


def test_get_bytes():
    resp = _DummyResponse(content=b"\x89PNG")
    session = _DummySession(resp)
    result = get_bytes(session, "https://example.com/img.png")
    assert result == b"\x89PNG"


def test_get_json():
    resp = _DummyResponse(json_data={"key": "value"})
    session = _DummySession(resp)
    result = get_json(session, "https://example.com/api")
    assert result == {"key": "value"}


def test_get_text_custom_timeout():
    resp = _DummyResponse(text="ok")
    session = _DummySession(resp)
    get_text(session, "https://example.com", timeout=5)
    assert session.last_kwargs.get("timeout") == 5
