from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from article_harvest.models import FetchContext
from article_harvest.sources.blogs.alignment_anthropic import fetch_alignment_anthropic
from article_harvest.sources.blogs.alphasignal_last_email import (
    _cleanup_markdown,
    _collapse_blank_lines,
    _is_pipe_separator,
    _is_table_rule,
    _trim_preamble,
)
from article_harvest.sources.blogs.claude_blog import fetch_claude_blog
from article_harvest.sources.blogs.cursor_blog import fetch_cursor_blog
from article_harvest.sources.blogs.founders_fund_anatomy import fetch_founders_fund
from article_harvest.sources.blogs.openai_dev_blog import fetch_openai_dev_blog
from article_harvest.sources.blogs.physical_intelligence import fetch_physical_intelligence

# -- helpers --


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
    def __init__(self, responses=None, default=None):
        self._responses = responses or {}
        self._default = default
        self.headers = {}

    def get(self, url, **kwargs):
        if url in self._responses:
            return self._responses[url]
        if self._default is not None:
            return self._default
        raise ValueError(f"Unmocked URL: {url}")


def _ctx(session):
    return FetchContext(session=session, run_id="test", now=datetime.utcnow())


# -- Claude Blog --


_CLAUDE_LISTING = """\
<html><body><main>
  <article><a href="/blog/post-one"><h2>Post One</h2></a></article>
  <article><a href="/blog/post-two"><h2>Post Two</h2></a></article>
  <article><a href="/blog/category/news">Category link</a></article>
</main></body></html>"""

_CLAUDE_ARTICLE = """\
<html><head>
<script type="application/ld+json">{"datePublished": "2026-01-15"}</script>
</head><body><main>
  <h1>The Real Title</h1>
  <p>Interesting article content goes here with enough text to verify.</p>
</main></body></html>"""


def test_fetch_claude_blog():
    session = _DummySession(
        responses={"https://claude.com/blog": _DummyResponse(text=_CLAUDE_LISTING)},
        default=_DummyResponse(text=_CLAUDE_ARTICLE),
    )
    items = fetch_claude_blog(_ctx(session))
    assert len(items) == 2
    assert items[0].title == "The Real Title"
    assert items[0].published_at == "2026-01-15"
    assert "Interesting article content" in items[0].content_markdown


# -- Cursor Blog --


_CURSOR_LISTING = """\
<html><body><main>
  <article><a href="/blog/composer-2"><h2>Composer 2</h2></a></article>
  <article><a href="/blog/cursor-3"><h2>Cursor 3</h2></a></article>
  <article><a href="/blog/topic/research">Topic link</a></article>
</main></body></html>"""

_CURSOR_ARTICLE = """\
<html><head>
<script type="application/ld+json">
{"@type": "BlogPosting", "datePublished": "2026-03-19T00:00:00.000Z"}
</script>
</head><body><article>
  <h1>Introducing Composer 2</h1>
  <time datetime="2026-03-19T00:00:00.000Z">Mar 19, 2026</time>
  <p>Composer 2 is now available in Cursor with frontier-level coding ability.</p>
</article></body></html>"""


def test_fetch_cursor_blog():
    session = _DummySession(
        responses={"https://cursor.com/blog": _DummyResponse(text=_CURSOR_LISTING)},
        default=_DummyResponse(text=_CURSOR_ARTICLE),
    )
    items = fetch_cursor_blog(_ctx(session))
    assert len(items) == 2
    assert items[0].title == "Introducing Composer 2"
    assert items[0].published_at == "2026-03-19"
    assert "Composer 2 is now available" in items[0].content_markdown


# -- OpenAI Developers Blog --


_OPENAI_LISTING = """\
<html><body><main>
  <a href="/blog/new-feature">New Feature</a>
  <a href="/blog/update">Update</a>
  <a href="/blog/topic/ai">Topic link</a>
  <a href="/docs/api">Docs link</a>
</main></body></html>"""

_OPENAI_ARTICLE = """\
<html><body><article>
  <h1>OpenAI Feature</h1>
  <p>Details about the new feature.</p>
</article></body></html>"""


def test_fetch_openai_dev_blog():
    session = _DummySession(
        responses={
            "https://developers.openai.com/blog": _DummyResponse(text=_OPENAI_LISTING),
        },
        default=_DummyResponse(text=_OPENAI_ARTICLE),
    )
    items = fetch_openai_dev_blog(_ctx(session))
    assert len(items) == 2
    assert items[0].title == "OpenAI Feature"
    assert "new feature" in items[0].content_markdown.lower()


# -- Alignment Anthropic --


_ALIGNMENT_LISTING = """\
<html><body><main>
  <h2>Articles</h2>
  <div class="date">April 2026</div>
  <a href="2026/automated-w2s/" class="note"><h3>Automated Weak-to-Strong</h3></a>
  <div class="date">March 2026</div>
  <a href="2026/abstractive-red-teaming/" class="note"><h3>Abstractive Red-Teaming</h3></a>
  <a href="https://arxiv.org/abs/2506.18032" class="paper"><h3>External Paper Title</h3></a>
</main></body></html>"""


def test_fetch_alignment_anthropic():
    session = _DummySession(
        responses={"https://alignment.anthropic.com/": _DummyResponse(text=_ALIGNMENT_LISTING)},
    )
    items = fetch_alignment_anthropic(_ctx(session))
    assert len(items) == 3

    internal = items[0]
    assert internal.url == "https://alignment.anthropic.com/2026/automated-w2s/"
    assert internal.title == "Automated Weak-to-Strong"
    assert internal.published_at == "2026-04-01"
    assert internal.content_markdown is None

    external = items[2]
    assert external.url == "https://arxiv.org/abs/2506.18032"
    assert external.title == "External Paper Title"
    assert external.published_at == "2026-03-01"


# -- Physical Intelligence --


_PI_LISTING = """\
<html><body><main>
  <a href="/blog/pi07">
    <div>
      <div title="π0.7: a Steerable Model with Emergent Capabilities">
        <span>π</span><sub>0.7</sub>: a Steerable Model with Emergent Capabilities
      </div>
      <div>April 16, 2026</div>
    </div>
    <p>A steerable robotic foundation model.</p>
  </a>
  <a href="/blog/openpi">
    <div>
      <div title="Open Sourcing π0">Open Sourcing π0</div>
      <div>February 4, 2025</div>
    </div>
  </a>
  <a href="/blog/page-abc123">Build artifact link</a>
  <a href="/blog/openpi">Duplicate slug</a>
</main></body></html>"""


def test_fetch_physical_intelligence():
    pi_url = "https://www.physicalintelligence.company/blog"
    session = _DummySession(responses={pi_url: _DummyResponse(text=_PI_LISTING)})
    items = fetch_physical_intelligence(_ctx(session))
    assert len(items) == 2

    first = items[0]
    assert first.url == "https://www.physicalintelligence.company/blog/pi07"
    assert first.title == "π0.7: a Steerable Model with Emergent Capabilities"
    assert first.published_at == "2026-04-16"

    second = items[1]
    assert second.url == "https://www.physicalintelligence.company/blog/openpi"
    assert second.title == "Open Sourcing π0"
    assert second.published_at == "2025-02-04"


# -- AlphaSignal helpers --


def test_is_table_rule_true():
    assert _is_table_rule("| --- | --- | --- | --- | --- |")


def test_is_table_rule_false_blank():
    assert not _is_table_rule("")


def test_is_table_rule_false_few_pipes():
    assert not _is_table_rule("| a |")


def test_is_pipe_separator_true():
    assert _is_pipe_separator("|  |  |")


def test_is_pipe_separator_false_has_text():
    assert not _is_pipe_separator("| hello |")


def test_is_pipe_separator_false_blank():
    assert not _is_pipe_separator("")


def test_trim_preamble_hey():
    lines = ["Welcome", "Hey there!", "Content"]
    assert _trim_preamble(lines) == ["Hey there!", "Content"]


def test_trim_preamble_daily_briefing():
    lines = ["Logo", "Your daily briefing is here", "Data"]
    assert _trim_preamble(lines) == ["Your daily briefing is here", "Data"]


def test_trim_preamble_no_match():
    lines = ["Content only", "More content"]
    assert _trim_preamble(lines) == lines


def test_collapse_blank_lines():
    lines = ["a", "", "", "", "b", "", "c"]
    assert _collapse_blank_lines(lines) == "a\n\nb\n\nc"


def test_cleanup_markdown():
    text = "Hey folks!\n| --- | --- | --- | --- | --- |\n\nContent\n|  |\n\n\nMore"
    result = _cleanup_markdown(text)
    assert "---" not in result
    assert "Hey folks!" in result
    assert "Content" in result
    assert "More" in result


# -- Founders Fund Anatomy --


def test_fetch_founders_fund():
    payload = [
        {
            "title": {"rendered": "<b>Deep Tech</b>"},
            "link": "https://foundersfund.com/anatomy/deep-tech",
            "date": "2026-01-10",
            "excerpt": {"rendered": "<p>Summary here</p>"},
            "content": {"rendered": "<p>Full content here</p>"},
        },
        {
            "title": {"rendered": "Second Post"},
            "link": "https://foundersfund.com/anatomy/second",
            "date": "2026-01-11",
            "excerpt": {"rendered": "<p>Another summary</p>"},
            "content": {"rendered": "<p>Another full post</p>"},
        },
    ]
    session = _DummySession(default=_DummyResponse(json_data=payload))
    items = fetch_founders_fund(_ctx(session))
    assert len(items) == 2
    assert items[0].title == "Deep Tech"
    assert items[0].published_at == "2026-01-10"
    assert items[0].content_markdown is not None
    assert "Full content" in items[0].content_markdown
    assert items[0].summary is not None


# -- 36Kr 资情留言板 --


# 北京时间 2026-05-26 07:30，此刻 UTC 仍是 05-25——用来锁住东八区口径。
_KR36_PUBLISH_MS = 1779751800000


def _kr36_page(state: dict) -> str:
    return f"<html><body><script>window.initialState = {json.dumps(state)}</script></body></html>"


def _kr36_listing(count: int) -> str:
    items = [
        {
            "itemId": 3825834410333062 + i,
            "templateMaterial": {
                "widgetTitle": f"资情留言板第{183 - i}期",
                "publishTime": _KR36_PUBLISH_MS,
                "content": "摘要",
                "author": "36Kr",
            },
        }
        for i in range(count)
    ]
    return _kr36_page(
        {"motifDetailData": {"data": {"motifArticleList": {"data": {"itemList": items}}}}}
    )


_KR36_ARTICLE = _kr36_page(
    {
        "articleDetail": {
            "articleDetailData": {"data": {"widgetContent": "<p>求购 Anthropic 老股份额</p>"}}
        }
    }
)


def test_kr36_motif_parses_listing_and_article():
    from article_harvest.sources.blogs.kr36_motif import KR36_MOTIF_URL, fetch_kr36_motif

    session = _DummySession(
        responses={KR36_MOTIF_URL: _DummyResponse(text=_kr36_listing(2))},
        default=_DummyResponse(text=_KR36_ARTICLE),
    )
    items = fetch_kr36_motif(_ctx(session))

    assert len(items) == 2
    assert items[0].title == "资情留言板第183期"
    assert items[0].url == "https://www.36kr.com/p/3825834410333062"
    # UTC 会算成 05-25；36 氪按北京时间发刊，必须是 05-26
    assert items[0].published_at == "2026-05-26"
    assert items[0].content_markdown is not None
    assert "Anthropic" in items[0].content_markdown


def test_kr36_motif_caps_at_limit():
    from article_harvest.sources.blogs.kr36_motif import (
        KR36_MOTIF_LIMIT,
        KR36_MOTIF_URL,
        fetch_kr36_motif,
    )

    session = _DummySession(
        responses={KR36_MOTIF_URL: _DummyResponse(text=_kr36_listing(20))},
        default=_DummyResponse(text=_KR36_ARTICLE),
    )
    assert len(fetch_kr36_motif(_ctx(session))) == KR36_MOTIF_LIMIT


def test_kr36_motif_keeps_item_when_article_body_missing():
    """正文抓不到时降级为纯元信息，不能整个源 fail。"""
    from article_harvest.sources.blogs.kr36_motif import KR36_MOTIF_URL, fetch_kr36_motif

    session = _DummySession(
        responses={KR36_MOTIF_URL: _DummyResponse(text=_kr36_listing(1))},
        default=_DummyResponse(text="<html><body>no state here</body></html>"),
    )
    items = fetch_kr36_motif(_ctx(session))

    assert len(items) == 1
    assert items[0].content_markdown is None
    assert items[0].title == "资情留言板第183期"


def test_kr36_motif_raises_on_broken_page():
    import pytest

    from article_harvest.errors import FetchError
    from article_harvest.sources.blogs.kr36_motif import fetch_kr36_motif

    session = _DummySession(default=_DummyResponse(text="<html><body>redesigned</body></html>"))
    with pytest.raises(FetchError):
        fetch_kr36_motif(_ctx(session))


# -- GitHub releases（上游依赖跟踪）--


def _atom(entries: list[tuple[str, str]]) -> bytes:
    body = "".join(
        f"<entry><title>{title}</title>"
        f"<link href='https://github.com/o/r/releases/tag/{title}'/>"
        f"<updated>{when}</updated><content type='html'>notes for {title}</content></entry>"
        for title, when in entries
    )
    feed = (
        "<?xml version='1.0' encoding='utf-8'?>"
        f"<feed xmlns='http://www.w3.org/2005/Atom'><title>Releases</title>{body}</feed>"
    )
    return feed.encode()


def _recent(days_ago: int = 0) -> str:
    moment = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_github_releases_drops_prereleases():
    """codex 一天 8 个 alpha，不过滤的话有内容的 stable 会被挤出 atom 窗口。"""
    from article_harvest.sources.blogs.github_releases import openclaw_releases_source

    feed = _atom(
        [
            ("openclaw 2026.9.3", _recent(0)),
            ("openclaw 2026.9.3-beta.2", _recent(1)),
            ("rust-v0.154.0-alpha.10.1", _recent(1)),
            ("v7.13.0-rc.1", _recent(2)),
            ("openclaw 2026.9.2", _recent(3)),
        ]
    )
    session = _DummySession(default=_DummyResponse(content=feed))
    items = openclaw_releases_source().fetch(_ctx(session))

    assert [item.title for item in items] == ["openclaw 2026.9.3", "openclaw 2026.9.2"]


def test_github_releases_respects_max_age():
    from article_harvest.sources.blogs.github_releases import pi_releases_source

    feed = _atom([("v0.85.1", _recent(1)), ("v0.70.0", _recent(60))])
    session = _DummySession(default=_DummyResponse(content=feed))
    items = pi_releases_source().fetch(_ctx(session))

    assert [item.title for item in items] == ["v0.85.1"]


def test_codex_uses_latest_stable_endpoint():
    """codex 走 API 的 latest 端点，它按定义跳过 prerelease。"""
    from article_harvest.sources.blogs.github_releases import codex_releases_source

    payload = {
        "name": "0.153.4",
        "tag_name": "rust-v0.153.4",
        "html_url": "https://github.com/openai/codex/releases/tag/rust-v0.153.4",
        "published_at": "2026-09-04T23:25:48Z",
        "body": "## Bug Fixes\n\n- Fixed the bundled model picker.",
    }
    session = _DummySession(default=_DummyResponse(json_data=payload))
    items = codex_releases_source().fetch(_ctx(session))

    assert len(items) == 1
    assert items[0].title == "0.153.4"
    assert items[0].published_at == "2026-09-04T23:25:48Z"
    assert items[0].content_markdown is not None
    assert "Bug Fixes" in items[0].content_markdown


def test_codex_raises_on_bad_payload():
    import pytest

    from article_harvest.errors import FetchError
    from article_harvest.sources.blogs.github_releases import codex_releases_source

    session = _DummySession(default=_DummyResponse(json_data={"message": "Not Found"}))
    with pytest.raises(FetchError):
        codex_releases_source().fetch(_ctx(session))


# -- Anthropic API Release Notes --


_ANTHROPIC_NOTES = """\
<html><body><main>
  <h2 id="overview">Overview</h2>
  <p>Ignored, not a dated section.</p>
  <h3 id="september-3-2026">September 3, 2026<span><button>copy</button></span></h3>
  <p>Version 1.30.0 of the <code>ant</code> CLI adds <code>ant apply</code>.</p>
  <ul><li>Writes a claude-lock.json lockfile.</li></ul>
  <h3 id="september-1-2026">September 1, 2026<span><button>copy</button></span></h3>
  <p>We launched Claude Fable 5.1.</p>
  <h3 id="not-a-date">Migration guides</h3>
  <p>Should be skipped.</p>
</main></body></html>"""


def test_anthropic_release_notes_splits_by_date():
    from article_harvest.sources.blogs.anthropic_api_release_notes import (
        fetch_anthropic_api_release_notes,
    )

    session = _DummySession(default=_DummyResponse(text=_ANTHROPIC_NOTES))
    items = fetch_anthropic_api_release_notes(_ctx(session))

    assert len(items) == 2
    assert items[0].published_at == "2026-09-03"
    assert items[0].url.endswith("#september-3-2026")
    assert items[0].content_markdown is not None
    assert "ant apply" in items[0].content_markdown
    # 下一节的内容不能漏进来
    assert "Fable" not in items[0].content_markdown
    assert items[1].published_at == "2026-09-01"


def test_anthropic_release_notes_raises_when_page_has_no_dates():
    import pytest

    from article_harvest.errors import FetchError
    from article_harvest.sources.blogs.anthropic_api_release_notes import (
        fetch_anthropic_api_release_notes,
    )

    session = _DummySession(
        default=_DummyResponse(text="<html><body><h3 id='x'>Nope</h3></body></html>")
    )
    with pytest.raises(FetchError):
        fetch_anthropic_api_release_notes(_ctx(session))


def test_github_releases_keeps_prereleases_when_repo_has_no_stable():
    """deepseek-harness 至今没发过正式版，但它的 alpha notes 是完整的「新增功能」章节。"""
    from article_harvest.sources.blogs.github_releases import deepseek_harness_releases_source

    feed = _atom(
        [
            ("dsh-v0.1.5-alpha.2", _recent(0)),
            ("dsh-v0.1.2-rc.1", _recent(2)),
        ]
    )
    session = _DummySession(default=_DummyResponse(content=feed))
    items = deepseek_harness_releases_source().fetch(_ctx(session))

    assert [item.title for item in items] == ["dsh-v0.1.5-alpha.2", "dsh-v0.1.2-rc.1"]


# -- GitHub 维护者 RFC --


class _GitHubFakeSession:
    """按顺序回放 REST 分页，并记录每次请求，用来断言 token 只随请求发往 api.github.com。"""

    def __init__(self, pages, graphql=None):
        self.pages = list(pages)
        self.graphql = graphql
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(("GET", url, params, headers))
        issues, next_url = self.pages.pop(0)
        response = _DummyResponse(json_data=issues)
        response.links = {"next": {"url": next_url}} if next_url else {}
        return response

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("POST", url, json, headers))
        return _DummyResponse(json_data=self.graphql)


def _gh_issue(number, association, *, created="2026-09-03T18:00:00Z", pull_request=False):
    issue = {
        "number": number,
        "title": f"Issue {number}",
        "html_url": f"https://github.com/anthropics/claude-code/issues/{number}",
        "author_association": association,
        "user": {"login": f"user{number}"},
        "state": "open",
        "comments": 3,
        "created_at": created,
        "body": f"# Community Update\n\nbody {number}",
    }
    if pull_request:
        issue["pull_request"] = {"url": f"https://api.github.com/pulls/{number}"}
    return issue


def test_claude_code_rfcs_filters_maintainers_and_keys_by_revision_day(monkeypatch):
    from article_harvest.sources.blogs.github_rfcs import claude_code_rfcs_source

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    session = _GitHubFakeSession(
        pages=[
            (
                [
                    _gh_issue(1, "NONE"),
                    _gh_issue(2, "CONTRIBUTOR"),
                    _gh_issue(3, "MEMBER", pull_request=True),
                ],
                "https://api.github.com/repositories/1/issues?page=2",
            ),
            (
                [
                    _gh_issue(4, "COLLABORATOR", created="2026-06-18T09:00:00Z"),
                    _gh_issue(2, "CONTRIBUTOR"),  # 翻页期间被更新，换页后重复出现
                ],
                None,
            ),
        ],
        graphql={
            "data": {
                "repository": {
                    "i2": {"lastEditedAt": "2026-09-09T23:32:00Z"},
                    "i4": {"lastEditedAt": None},
                }
            }
        },
    )
    items = claude_code_rfcs_source().fetch(_ctx(session))

    base = "https://github.com/anthropics/claude-code/issues"
    # 编辑过的按最后编辑日，从未编辑的按创建日；NONE 和 PR 被滤掉；重复只留一条
    assert [item.url for item in items] == [f"{base}/2#rev-2026-09-09", f"{base}/4#rev-2026-06-18"]
    assert items[0].published_at == "2026-09-09"
    assert items[0].content_markdown is not None
    assert "Community Update" in items[0].content_markdown

    gets = [call for call in session.calls if call[0] == "GET"]
    assert len(gets) == 2
    assert gets[0][2]["since"].endswith("Z")
    assert gets[0][2]["state"] == "all"
    assert gets[1][2] is None  # next 链接自带查询参数


def test_github_rfcs_sends_token_only_per_request_to_api_github(monkeypatch):
    """ingest 的 session 是全部源共用的，token 挂到 session 上会被发给其他站点。"""
    from article_harvest.sources.blogs.github_rfcs import claude_code_rfcs_source

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    session = _GitHubFakeSession(
        pages=[([_gh_issue(2, "CONTRIBUTOR")], None)],
        graphql={"data": {"repository": {"i2": {"lastEditedAt": None}}}},
    )
    claude_code_rfcs_source().fetch(_ctx(session))

    assert session.headers == {}
    assert [call[0] for call in session.calls] == ["GET", "POST"]
    for _method, url, _body, headers in session.calls:
        assert url.startswith("https://api.github.com/")
        assert headers["Authorization"] == "Bearer test-token"


def test_pi_rfcs_excludes_contributors_and_skips_graphql_when_empty(monkeypatch):
    """开源仓库的 CONTRIBUTOR 包含外部开发者；没有候选时不发 GraphQL。"""
    from article_harvest.sources.blogs.github_rfcs import pi_rfcs_source

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    session = _GitHubFakeSession(
        pages=[([_gh_issue(1, "CONTRIBUTOR"), _gh_issue(2, "NONE")], None)]
    )

    assert pi_rfcs_source().fetch(_ctx(session)) == []
    assert [call[0] for call in session.calls] == ["GET"]


def test_github_rfcs_fails_before_any_request_without_token(monkeypatch):
    import pytest

    from article_harvest.errors import FetchError
    from article_harvest.sources.blogs.github_rfcs import claude_code_rfcs_source

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    session = _GitHubFakeSession(pages=[])
    with pytest.raises(FetchError):
        claude_code_rfcs_source().fetch(_ctx(session))
    assert session.calls == []


def test_github_rfcs_raises_instead_of_truncating(monkeypatch):
    import pytest

    from article_harvest.errors import FetchError
    from article_harvest.sources.blogs import github_rfcs

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(github_rfcs, "_MAX_PAGES", 1)
    session = _GitHubFakeSession(
        pages=[([], "https://api.github.com/repositories/1/issues?page=2")]
    )
    with pytest.raises(FetchError):
        github_rfcs.claude_code_rfcs_source().fetch(_ctx(session))
