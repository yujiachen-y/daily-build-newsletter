from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import requests
from markdownify import markdownify as md

from ...errors import FetchError
from ...http import get_text
from ...models import BlogItem, FetchContext, Source

# 36 氪「资情留言板」话题页：一级市场老股与基金 LP 份额的求购 / 转让挂牌。
# 与 techcrunch-fundings 等源互补——那些报道已完成的融资轮，这里是尚未成交的买方报价意愿。
KR36_MOTIF_URL = "https://www.36kr.com/motif/1917710261526274"
KR36_ARTICLE_URL = "https://www.36kr.com/p/{item_id}"

# ponytail: 月更源（实测第 179–183 期间隔 3–6 周），取 5 期约覆盖半年。
# 若改成日更节奏或要回溯更久，调大这个数即可——列表页一次返回 20 条。
KR36_MOTIF_LIMIT = 5

# 36 氪是 SSR 页面，列表与正文都内嵌在 window.initialState 里，无需 RSSHub 或无头浏览器。
_STATE_RE = re.compile(r"window\.initialState\s*=\s*(\{.*?\})\s*</script>", re.S)

# 期号日期按东八区解读——36 氪按北京时间发刊，"第 183 期发布于 5 月 26 日"以此为准。
_CST = timezone(timedelta(hours=8))


def source() -> Source:
    return Source(
        id="kr36-motif",
        name="36Kr 资情留言板",
        kind="blog",
        method="html",
        fetch=fetch_kr36_motif,
    )


def fetch_kr36_motif(ctx: FetchContext) -> list[BlogItem]:
    state = _parse_state(get_text(ctx.session, KR36_MOTIF_URL))
    try:
        entries = state["motifDetailData"]["data"]["motifArticleList"]["data"]["itemList"]
    except (KeyError, TypeError) as exc:
        raise FetchError("36Kr motif list missing itemList") from exc

    items: list[BlogItem] = []
    for entry in entries[:KR36_MOTIF_LIMIT]:
        item = _build_item(ctx, entry)
        if item:
            items.append(item)

    if not items:
        raise FetchError("36Kr motif returned no items")
    return items


def _build_item(ctx: FetchContext, entry: dict) -> BlogItem | None:
    material = entry.get("templateMaterial") or {}
    title = material.get("widgetTitle")
    item_id = entry.get("itemId")
    if not title or not item_id:
        return None

    url = KR36_ARTICLE_URL.format(item_id=item_id)
    return BlogItem(
        title=title,
        url=url,
        published_at=_to_date(material.get("publishTime")),
        author=material.get("author"),
        summary=material.get("content") or None,
        content_markdown=_fetch_content(ctx, url),
    )


def _fetch_content(ctx: FetchContext, url: str) -> str | None:
    """正文抓取失败时降级为纯元信息，不让整个源 fail。"""
    try:
        state = _parse_state(get_text(ctx.session, url))
        html = state["articleDetail"]["articleDetailData"]["data"]["widgetContent"]
    except (FetchError, KeyError, TypeError, requests.RequestException):
        return None
    if not isinstance(html, str):
        return None
    return md(html).strip() or None


def _parse_state(html: str) -> dict:
    match = _STATE_RE.search(html)
    if not match:
        raise FetchError("36Kr page missing window.initialState")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise FetchError("36Kr initialState is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise FetchError("36Kr initialState is not an object")
    return payload


def _to_date(publish_time: object) -> str | None:
    """publishTime 是毫秒时间戳。"""
    if isinstance(publish_time, bool) or not isinstance(publish_time, (int, float)):
        return None
    return datetime.fromtimestamp(publish_time / 1000, tz=_CST).date().isoformat()
