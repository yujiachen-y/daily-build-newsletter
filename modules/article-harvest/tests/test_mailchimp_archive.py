from __future__ import annotations

from datetime import datetime

from article_harvest.models import FetchContext
from article_harvest.sources.blogs.mailchimp_archive import mailchimp_archive_html_to_markdown
from article_harvest.sources.rss import fetch_rss


class DummySession:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def get(self, url: str, timeout: int = 20):
        return DummyResponse(self.payload)


class DummyResponse:
    def __init__(self, payload: bytes) -> None:
        self.content = payload

    def raise_for_status(self):
        return None


def test_mailchimp_archive_html_to_markdown_strips_layout_tables_and_footer():
    html = """
    <html><body>
      <td class="mcnTextContent">
        <h1>This Week at YC</h1>
        <p>Intro <a href="https://example.com/a">A</a>.</p>
        <table>
          <tr><td></td><td></td><td></td></tr>
          <tr><td>One</td><td></td><td>F2025</td></tr>
        </table>
      </td>
      <td class="mcnTextContent">
        <em>Copyright</em> Want to change how you receive these emails?
        You can <a href="https://example.com/prefs">update your preferences</a> or
        <a href="https://example.com/unsub">unsubscribe from this list</a>.
      </td>
    </body></html>
    """

    rendered = mailchimp_archive_html_to_markdown(html)
    assert "This Week at YC" in rendered
    assert "[A](https://example.com/a)" in rendered
    assert "unsubscribe" not in rendered.lower()
    assert "update your preferences" not in rendered.lower()

    # Critical: avoid Markdown table artifacts like `|  |` and `| --- |`.
    assert "| ---" not in rendered
    assert "\n|" not in rendered


def test_fetch_rss_accepts_html_to_markdown_override():
    html = """
    <td class="mcnTextContent">
      <h1>This Week at YC</h1>
      <table>
        <tr><td></td><td></td></tr>
        <tr><td>One</td><td>Two</td></tr>
      </table>
    </td>
    """
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel>
        <title>Example</title>
        <item>
          <title>Sample Post</title>
          <link>https://example.com/post</link>
          <pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate>
          <content:encoded><![CDATA[{html}]]></content:encoded>
        </item>
      </channel>
    </rss>
    """
    session = DummySession(feed.encode("utf-8"))
    ctx = FetchContext(session=session, run_id="run", now=datetime.utcnow())
    items = fetch_rss(
        ctx,
        "https://example.com/feed",
        html_to_markdown=mailchimp_archive_html_to_markdown,
    )
    assert len(items) == 1
    assert items[0].content_markdown
    assert "| ---" not in items[0].content_markdown
