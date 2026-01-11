from __future__ import annotations

from article_ingest.extract import extract_markdown
from article_ingest.text_processing import detect_blocked_text, hash_content, normalize_markdown


def test_normalize_markdown_trims_whitespace():
    normalized = normalize_markdown("hello  \r\nworld\r\n")
    assert normalized == "hello\nworld\n"


def test_hash_content_is_stable():
    first = hash_content("hello\n")
    second = hash_content("hello")
    assert first == second


def test_detect_blocked_text_short():
    variants = [
        "You can't perform that action at this time.",
        "You cant perform that action at this time.",
        "You can\u2019t perform that action at this time.",
        "You can\u201a\u00c4\u00b4t perform that action at this time.",
    ]
    for text in variants:
        assert detect_blocked_text(text) is not None


def test_detect_blocked_text_other_patterns():
    variants = [
        "Attention Required! Please enable JavaScript.",
        "Checking your browser before accessing example.com.",
        "Access denied.",
    ]
    for text in variants:
        assert detect_blocked_text(text) is not None


def test_extract_markdown_strips_scripts():
    html = (
        "<html><body><h1>Title</h1><script>bad()</script>"
        "<p>Hello world " * 5
        + "</p></body></html>"
    )
    markdown = extract_markdown(html)
    assert "Title" in markdown
    assert "Hello" in markdown
