from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from ...errors import FetchError
from ...models import BlogItem, FetchContext, Source

# 维护者 RFC 追踪：日报「上游动态」里"快要来什么"的一半，releases 是"已经发了什么"的一半。
# 典型样本是 anthropics/claude-code#91870：正文随进度追加 "Community Update"，里面的
# function hooks / Claude Mods 在全部 390 版 CHANGELOG 里一次都没出现，mods/ 目录的代码却已提交。
#
# GitHub 不给 issue 出 feed（issues.atom 返回 406，discussions.atom 返回 404），只能走 API。
#
# ponytail: 只跟正文。#91870 的作者在 156 条评论里回了 24 条，这些回复不进 harvest；
# 要跟就在 fetch 里再查一次 comments，同样按 author_association 过滤。
_ISSUES_URL = "https://api.github.com/repos/{repo}/issues"
_GRAPHQL_URL = "https://api.github.com/graphql"
_TOKEN_ENV = "GITHUB_TOKEN"

# ponytail: 26h = 每天跑一次 + 2h 余量。连着两天没跑，只在那两天有动静的 RFC 会漏；
# 真漏了就调大窗口，代价是 claude-code 每 24h 约 1000 个有更新的 issue、每天多翻约 10 页。
_SINCE_HOURS = 26
_PER_PAGE = 100
# claude-code 实测 24h 约 11 页，给到 3 倍。撞上限就报错，不静默截断。
_MAX_PAGES = 30

# 维护者身份按仓库区分，因为 CONTRIBUTOR 在不同仓库含义不同：
# - claude-code：24h 内 1033 个有更新的 issue 里只有 1 个作者不是 NONE，就是 #91870（CONTRIBUTOR）。
# - 开源仓库：CONTRIBUTOR 包含提过 PR 的外部开发者（codex 实测 7 天 8 个，全是用户报 bug）。
_MAINTAINERS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
_MAINTAINERS_AND_CONTRIBUTORS = _MAINTAINERS | {"CONTRIBUTOR"}


def _maintainer_rfcs_source(
    source_id: str, name: str, repo: str, associations: frozenset[str]
) -> Source:
    def fetch(ctx: FetchContext) -> list[BlogItem]:
        headers = _auth_headers()
        issues = _list_maintainer_issues(ctx, repo, associations, headers)
        if not issues:
            return []
        edited = _last_edited_at(ctx, repo, [issue["number"] for issue in issues], headers)
        return [_to_item(issue, edited.get(issue["number"])) for issue in issues]

    return Source(id=source_id, name=name, kind="blog", method="api", fetch=fetch)


def _auth_headers() -> dict[str, str]:
    token = os.environ.get(_TOKEN_ENV)
    if not token:
        # 在发任何请求之前失败：lastEditedAt 走 GraphQL，而 GraphQL 不接受匿名请求。
        raise FetchError(
            f"{_TOKEN_ENV} not set; maintainer RFC tracking needs the GitHub GraphQL API"
        )
    # 只随单个请求发往 api.github.com。ingest 的 session 是全部源共用的，挂到 session 上
    # 会把 token 一并发给 36kr、docs.claude.com 等其他站点。
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def _list_maintainer_issues(
    ctx: FetchContext, repo: str, associations: frozenset[str], headers: dict[str, str]
) -> list[dict[str, Any]]:
    since = _as_utc(ctx.now) - timedelta(hours=_SINCE_HOURS)
    url = _ISSUES_URL.format(repo=repo)
    params: dict[str, Any] | None = {
        "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "state": "all",
        "sort": "updated",
        "direction": "desc",
        "per_page": _PER_PAGE,
    }
    # 按 number 去重：翻页期间 issue 可能因为新的更新换到别的页，同一个会出现两次。
    found: dict[int, dict[str, Any]] = {}
    for _ in range(_MAX_PAGES):
        response = ctx.session.get(url, params=params, headers=headers, timeout=20)
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise FetchError(f"GitHub issues payload invalid for {repo}")
        for issue in page:
            if "pull_request" in issue or issue.get("author_association") not in associations:
                continue
            found.setdefault(int(issue["number"]), issue)
        next_url = (response.links.get("next") or {}).get("url")
        if not next_url:
            return list(found.values())
        url, params = next_url, None  # next 链接自带查询参数
    raise FetchError(f"GitHub issues for {repo} exceeded {_MAX_PAGES} pages in {_SINCE_HOURS}h")


def _last_edited_at(
    ctx: FetchContext, repo: str, numbers: list[int], headers: dict[str, str]
) -> dict[int, str]:
    """用一次 GraphQL 请求（别名）批量取候选 issue 的 lastEditedAt。"""
    owner, name = repo.split("/", 1)
    fields = " ".join(f"i{int(n)}: issue(number: {int(n)}) {{ lastEditedAt }}" for n in numbers)
    query = f'query {{ repository(owner: "{owner}", name: "{name}") {{ {fields} }} }}'
    response = ctx.session.post(_GRAPHQL_URL, json={"query": query}, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    nodes = data.get("repository") if isinstance(data, dict) else None
    if not isinstance(nodes, dict):
        raise FetchError(f"GitHub GraphQL returned no repository data for {repo}")
    edited: dict[int, str] = {}
    for number in numbers:
        node = nodes.get(f"i{int(number)}")
        if isinstance(node, dict) and node.get("lastEditedAt"):
            edited[number] = str(node["lastEditedAt"])
    return edited


def _to_item(issue: dict[str, Any], last_edited_at: str | None) -> BlogItem:
    # 按「修订日」出条目，而不是一个 issue 一条：storage 按 URL 去重，已存在的 URL 不会刷新正文
    # （_update_empty_content 只修空文件和残缺文件）。URL 如果就是 issue 本身，#91870 会在
    # 09-03 存一次，09-09 追加的 Community Update 被静默丢弃。
    # 用日期不用时间戳：#91870 的 5 次编辑里有 3 次挤在 09-09 的 40 分钟内。
    revised = (last_edited_at or str(issue["created_at"]))[:10]
    return BlogItem(
        title=str(issue["title"]),
        url=f"{issue['html_url']}#rev-{revised}",
        published_at=revised,
        author=(issue.get("user") or {}).get("login"),
        summary=(
            f"{issue.get('author_association')} · {issue.get('state')} · "
            f"{issue.get('comments', 0)} comments"
        ),
        content_markdown=(issue.get("body") or "").strip() or None,
    )


def _as_utc(moment: datetime) -> datetime:
    # ingest 传进来的是 naive 的 datetime.utcnow()
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def claude_code_rfcs_source() -> Source:
    return _maintainer_rfcs_source(
        "claude-code-rfcs",
        "Claude Code Maintainer RFCs",
        "anthropics/claude-code",
        _MAINTAINERS_AND_CONTRIBUTORS,
    )


def pi_rfcs_source() -> Source:
    # mitsuhiko / badlogic 的设计与 meta issue，实测 7 天内约 2 条。
    return _maintainer_rfcs_source(
        "pi-rfcs", "pi Maintainer Issues", "earendil-works/pi", _MAINTAINERS
    )
