from __future__ import annotations

import re

from ...errors import FetchError
from ...http import get_json
from ...models import BlogItem, FetchContext, Source
from ..rss import fetch_rss

# 上游依赖跟踪：日报「上游动态」小节的数据来源。
# 与 github-trending 的区别是清单固定——trending 回答"今天什么火了"，
# 这里回答"我在用的东西变了什么"。
#
# GitHub 的 releases.atom 免认证、标准 RSS，不需要 API token 或本地 clone。
# （~/Workspace 下的本地 clone 不能当数据源：实测 44 个 repo 全部从未 fetch，
#  codex 落后 1 个月、pi 3.5 个月、openclaw 4.5 个月，且部分是 SSH remote。）
_RELEASES_ATOM = "https://github.com/{repo}/releases.atom"
_LATEST_RELEASE_API = "https://api.github.com/repos/{repo}/releases/latest"

# ponytail: 14 天窗口，防的是首抓回填一堆旧版本。
_MAX_AGE_DAYS = 14

# alpha/beta 的 release notes 实测是空壳（codex 的 alpha 只有 "Release 0.154.0-alpha.11"
# 这 23 字节），stable 才带 "## New Features"。
_PRERELEASE_RE = re.compile(r"-(alpha|beta|rc|canary|nightly|pre)\b", re.IGNORECASE)


def _releases_source(
    source_id: str,
    name: str,
    repo: str,
    *,
    latest_only: bool = False,
    stable_only: bool = True,
) -> Source:
    """三种模式对应三种实测到的仓库行为：

    - 默认（atom + 滤掉 prerelease）：绝大多数仓库。
    - latest_only：alpha 密集到淹没 atom 窗口的仓库，见 codex_releases_source。
    - stable_only=False：还没发过正式版的仓库，见 deepseek_harness_releases_source。
    """
    fetch = _fetch_latest_stable(repo) if latest_only else _fetch_recent(repo, stable_only)
    return Source(id=source_id, name=name, kind="blog", method="rss", fetch=fetch)


def _fetch_recent(repo: str, stable_only: bool):
    feed_url = _RELEASES_ATOM.format(repo=repo)

    def fetch(ctx: FetchContext) -> list[BlogItem]:
        items = fetch_rss(ctx, feed_url, max_age_days=_MAX_AGE_DAYS)
        if not stable_only:
            return items
        return [item for item in items if not _PRERELEASE_RE.search(item.title)]

    return fetch


def _fetch_latest_stable(repo: str):
    """GitHub 的 /releases/latest 按定义跳过 draft 和 prerelease，正好绕开 alpha 洪水。

    ponytail: 只回最新一条，同一天发两个 stable 就会漏掉前一个。真开始漏了再翻页
    /releases（注意 codex 的 per_page=30 响应有 10MB，notes 太长），目前 codex 的
    stable 约一天一个，够用。
    """
    api_url = _LATEST_RELEASE_API.format(repo=repo)

    def fetch(ctx: FetchContext) -> list[BlogItem]:
        payload = get_json(ctx.session, api_url)
        if not isinstance(payload, dict) or not payload.get("html_url"):
            raise FetchError(f"GitHub latest release payload invalid for {repo}")
        title = payload.get("name") or payload.get("tag_name")
        if not title:
            return []
        return [
            BlogItem(
                title=str(title),
                url=str(payload["html_url"]),
                published_at=payload.get("published_at"),
                content_markdown=(payload.get("body") or "").strip() or None,
            )
        ]

    return fetch


def codex_releases_source() -> Source:
    # codex 一天发 8 个 alpha，releases.atom 那 10 条会被 alpha 占满——实测当前
    # 10 条无一 stable，过滤后 stored=0。所以这个源单独走 API 的 latest 端点。
    return _releases_source(
        "codex-releases", "OpenAI Codex Releases", "openai/codex", latest_only=True
    )


def openclaw_releases_source() -> Source:
    return _releases_source("openclaw-releases", "openclaw Releases", "openclaw/openclaw")


def pi_releases_source() -> Source:
    return _releases_source("pi-releases", "pi-monorepo Releases", "earendil-works/pi")


def openai_node_releases_source() -> Source:
    return _releases_source(
        "openai-node-releases", "OpenAI Node SDK Releases", "openai/openai-node"
    )


def deepseek_harness_releases_source() -> Source:
    # 这个仓库至今没发过正式版（/releases/latest 返回 404），14 条 release 全是
    # alpha/rc——但它的 alpha notes 是中英双语的完整「新增功能」章节（3.5–12.5KB），
    # 跟 codex 那种 23 字节空壳完全不同，所以这里不过滤 prerelease。
    # 等它发出 1.0 之后可以把 stable_only 改回默认。
    return _releases_source(
        "deepseek-harness-releases",
        "DeepSeek Harness Releases",
        "deepseek-ai/deepseek-harness",
        stable_only=False,
    )


def kimi_code_releases_source() -> Source:
    return _releases_source("kimi-code-releases", "Kimi Code Releases", "MoonshotAI/kimi-code")


def hyperframes_releases_source() -> Source:
    return _releases_source(
        "hyperframes-releases", "HyperFrames Releases", "heygen-com/hyperframes"
    )


def claude_code_releases_source() -> Source:
    return _releases_source(
        "claude-code-releases", "Claude Code Releases", "anthropics/claude-code"
    )
