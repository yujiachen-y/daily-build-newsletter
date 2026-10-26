from __future__ import annotations

import re

from ...models import BlogItem, FetchContext, Source
from ..rss import fetch_rss

# Agent skill 仓库的演进追踪：这类仓库很少发 release（pstack 一个都没有，mattpocock/skills
# 10-04 发完 v1.3.1 后 main 上仍在改），变化只体现在 commit 里，所以跟分支的 commits.atom。
# 同样免认证；atom 只给最近 20 条，commit message 就是正文，不含 diff。
_COMMITS_ATOM = "https://github.com/{repo}/commits/{branch}.atom"

# ponytail: 14 天窗口，与 github_releases 一致，防首抓回填。
_MAX_AGE_DAYS = 14

# merge commit 的信息与被合进来的那条 commit 重复（pstack 的 "Merge PR #15" 对应 da3ef14）。
_MERGE_RE = re.compile(r"^Merge\b")


def _commits_source(source_id: str, name: str, repo: str, branch: str = "main") -> Source:
    feed_url = _COMMITS_ATOM.format(repo=repo, branch=branch)

    def fetch(ctx: FetchContext) -> list[BlogItem]:
        items = fetch_rss(ctx, feed_url, max_age_days=_MAX_AGE_DAYS)
        return [item for item in items if not _MERGE_RE.match(item.title.strip())]

    return Source(id=source_id, name=name, kind="blog", method="rss", fetch=fetch)


def pstack_commits_source() -> Source:
    # Cursor 插件 pstack 的镜像，"upstream: cursor/plugins/pstack @ <sha>" 是同步上游的 commit。
    return _commits_source("pstack-commits", "pstack Commits", "backnotprop/pstack")


def mattpocock_skills_commits_source() -> Source:
    return _commits_source(
        "mattpocock-skills-commits", "mattpocock/skills Commits", "mattpocock/skills"
    )
