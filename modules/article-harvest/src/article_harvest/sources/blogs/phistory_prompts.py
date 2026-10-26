from __future__ import annotations

import difflib
from datetime import timedelta
from itertools import groupby

from ...errors import FetchError
from ...http import get_json, get_text
from ...models import BlogItem, FetchContext, Source
from ...time_utils import parse_datetime

# 各 coding-agent harness 的 system prompt 变更追踪（日报「上游动态」的又一半：
# releases 说"发了什么"，这里说"提示词里实际改了什么"）。数据来自 WEIFENG2333/phistory，
# 它每小时用 claude-tap 抓一次各 CLI 新版本的真实请求并存成 captures/<agent>/<ver>/.../prompt.md。
# 我们不自己抓，只拿 prompt.md 跟上一版做 diff；两版一字不差的不出 item（没变就不是新闻）。
_RAW = "https://raw.githubusercontent.com/WEIFENG2333/phistory/main/"
_TREE = "https://github.com/WEIFENG2333/phistory/tree/main/"

# ponytail: 只跟 default 变体（各 CLI 默认的终端形态）。claude-code 另有 sdk 等变体，
# 要跟就放开这个常量，代价是每个版本多一份 diff。
_VARIANT = "default"
# ponytail: 14 天窗口，防的是首抓回填一堆旧版本，与 github_releases 一致。
_MAX_AGE_DAYS = 14
# prompt.md 实测约 150KB（含 tool 定义），一次大改的 diff 能到几十 KB。截断时在正文里明说，
# 不静默丢；完整 diff 看 item 的 url。
_MAX_DIFF_CHARS = 30_000


def source() -> Source:
    def fetch(ctx: FetchContext) -> list[BlogItem]:
        index = get_json(ctx.session, _RAW + "captures/index.json", timeout=60)
        captures = index.get("captures") if isinstance(index, dict) else None
        if not captures:
            raise FetchError("phistory captures/index.json has no captures")

        cutoff = ctx.now.replace(tzinfo=None) - timedelta(days=_MAX_AGE_DAYS)
        cache: dict[str, str] = {}

        def prompt(entry: dict) -> str:
            path = entry["prompt"]
            if path not in cache:
                cache[path] = get_text(ctx.session, _RAW + path, timeout=60)
            return cache[path]

        items: list[BlogItem] = []
        key = lambda c: c["agent_id"]  # noqa: E731
        default = [c for c in captures if c["variant_id"] == _VARIANT and c.get("published_at")]
        for _, group in groupby(sorted(default, key=lambda c: (key(c), c["published_at"])), key):
            versions = list(group)
            for prev, cur in zip(versions, versions[1:]):
                if parse_datetime(cur["published_at"]).replace(tzinfo=None) < cutoff:
                    continue
                item = _diff_item(cur, prev["version"], prompt(prev), prompt(cur))
                if item:
                    items.append(item)
        return items

    return Source(
        id="phistory-prompts", name="Phistory Prompt Diffs", kind="blog", method="api", fetch=fetch
    )


def _diff_item(cur: dict, prev_version: str, old: str, new: str) -> BlogItem | None:
    diff = list(
        difflib.unified_diff(
            old.splitlines(), new.splitlines(), f"{prev_version}", cur["version"], n=1, lineterm=""
        )
    )
    if not diff:
        return None
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    body = "\n".join(diff)
    if len(body) > _MAX_DIFF_CHARS:
        body = body[:_MAX_DIFF_CHARS] + f"\n... [diff truncated at {_MAX_DIFF_CHARS} chars]"
    title = f"{cur['agent']} {cur['version']} system prompt (+{added}/-{removed} vs {prev_version})"
    tree = _TREE + cur["prompt"].rsplit("/", 1)[0]
    return BlogItem(
        title=title,
        url=tree,
        published_at=cur["published_at"],
        content_markdown=(
            f"Diff of `prompt.md` against {prev_version} ({tree}):\n\n```diff\n{body}\n```"
        ),
    )
