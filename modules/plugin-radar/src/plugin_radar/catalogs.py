"""Official plugin catalogs: what each agent's own marketplace lists, and what changed.

Claude Code, Codex and ZCode publish their official marketplaces as a JSON file in a public
GitHub repo, so the git history answers "what was listed in the last 7 days" on the very first
run. Kimi only has a public showcase page, so its changes start from the second run.

Claude's install counts (`plugin-details.json`, the file Claude Code's /plugin screen sorts by)
are tracked too, but Anthropic stopped regenerating that file on 2026-10-21, and the numbers on
claude.com/marketplace have not moved since at least 2026-09-29 (Internet Archive captures).
The report states the file's age instead of treating identical numbers as "no change".
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from typing import Any

import requests

from .http import get_json, get_text
from .storage import Storage, iso, parse_iso, utc_now

CATALOGS: dict[str, dict[str, str]] = {
    "claude": {
        "repo": "anthropics/claude-plugins-official",
        "path": ".claude-plugin/marketplace.json",
        "label": "Claude Code 官方市场",
    },
    "codex": {
        "repo": "openai/plugins",
        "path": ".agents/plugins/marketplace.json",
        "label": "Codex 官方插件目录",
    },
    "zcode": {
        "repo": "zai-org/zcode-plugins",
        "path": "marketplace.json",
        "label": "ZCode 官方市场",
    },
}
RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"
API = "https://api.github.com/repos/{repo}/commits"
MAX_VERSIONS = 60
KIMI_URL = "https://www.kimi.com/features/plugins"
CLAUDE_STATS_URL = (
    "https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/"
    "plugin-stats/plugin-details.json"
)
_GITHUB_RE = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?]|$)")


def github_headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def repo_of(entry: dict[str, Any], catalog_repo: str) -> str | None:
    """owner/repo that hosts a plugin entry's source, if it is on GitHub."""
    source = entry.get("source")
    if isinstance(source, str):
        return catalog_repo if source.startswith("./") else _github_repo(source)
    if isinstance(source, dict):
        if source.get("repo"):
            return str(source["repo"]).strip("/")
        for key in ("url", "path"):
            repo = _github_repo(str(source.get(key) or ""))
            if repo:
                return repo
        if source.get("source") == "local":
            return catalog_repo
    return _github_repo(str(entry.get("homepage") or entry.get("repository") or ""))


def _github_repo(text: str) -> str | None:
    match = _GITHUB_RE.search(text)
    return f"{match.group(1)}/{match.group(2)}" if match else None


def plugin_map(data: dict[str, Any], catalog_repo: str) -> dict[str, dict[str, Any]]:
    out = {}
    for entry in data.get("plugins") or []:
        name = entry.get("name")
        if not name:
            continue
        desc = entry.get("description_i18n") or {}
        out[name] = {
            "description": " ".join(
                str(desc.get("zh") or desc.get("zh-CN") or entry.get("description") or "").split()
            )[:200],
            "category": entry.get("category"),
            "version": entry.get("version"),
            "repo": repo_of(entry, catalog_repo),
            "external": repo_of(entry, catalog_repo) not in (None, catalog_repo),
        }
    return out


def diff_events(
    versions: list[tuple[dict[str, Any], dict[str, dict[str, Any]]]],
) -> tuple[dict[str, dict], dict[str, dict]]:
    """First commit that added / last commit that removed each name, oldest version first."""
    added: dict[str, dict] = {}
    removed: dict[str, dict] = {}
    for (_, before), (commit, after) in zip(versions, versions[1:]):
        for name in after.keys() - before.keys():
            added.setdefault(name, commit)
            removed.pop(name, None)
        for name in before.keys() - after.keys():
            removed[name] = commit
            added.pop(name, None)
    return added, removed


def fetch_catalog(
    session: requests.Session,
    storage: Storage,
    day: str,
    key: str,
    *,
    token: str | None = None,
    window_days: int = 7,
) -> dict[str, Any]:
    cfg = CATALOGS[key]
    repo, path = cfg["repo"], cfg["path"]
    observed = utc_now()
    since = observed - timedelta(days=window_days)
    headers = github_headers(token)
    commits = get_json(
        session,
        API.format(repo=repo),
        params={"path": path, "since": iso(since), "per_page": 100},
        headers=headers,
    )
    base = get_json(
        session,
        API.format(repo=repo),
        params={"path": path, "until": iso(since), "per_page": 1},
        headers=headers,
    )
    head_text = get_text(session, RAW.format(repo=repo, ref="HEAD", path=path))
    head = plugin_map(json.loads(head_text), repo)
    chain = [_commit_info(c) for c in reversed(commits or [])]
    if len(chain) > MAX_VERSIONS:  # keep the newest; older adds then date to the window start
        chain = chain[-MAX_VERSIONS:]
    versions: list[tuple[dict[str, Any], dict[str, dict[str, Any]]]] = []
    if base:
        base_info = _commit_info(base[0])
        versions.append((base_info, _plugins_at(session, repo, path, base_info["sha"])))
    for info in chain[:-1]:
        versions.append((info, _plugins_at(session, repo, path, info["sha"])))
    if chain:
        versions.append((chain[-1], head))
    added, removed = diff_events(versions) if len(versions) > 1 else ({}, {})
    return {
        "source": f"catalog-{key}",
        "day": day,
        "origin": "live",
        "observed_at": iso(observed),
        "repo": repo,
        "path": path,
        "label": cfg["label"],
        "window_days": window_days,
        "window_start": iso(since),
        "commits_in_window": len(commits or []),
        "plugins": head,
        "added": [{"name": n, **head[n], **_event(added[n])} for n in sorted(added) if n in head],
        "removed": [{"name": n, **_event(removed[n])} for n in sorted(removed) if n not in head],
        "raw": [storage.save_raw(day, f"catalog-{key}.json", head_text)],
    }


def _commit_info(commit: dict[str, Any]) -> dict[str, Any]:
    info = commit.get("commit") or {}
    message = (info.get("message") or "").splitlines()
    return {
        "sha": commit.get("sha"),
        "date": ((info.get("committer") or info.get("author") or {}).get("date")),
        "message": message[0][:120] if message else "",
        "url": commit.get("html_url"),
    }


def _event(info: dict[str, Any]) -> dict[str, Any]:
    return {"date": info.get("date"), "commit": info.get("url"), "message": info.get("message")}


def _plugins_at(
    session: requests.Session, repo: str, path: str, sha: str
) -> dict[str, dict[str, Any]]:
    text = get_text(session, RAW.format(repo=repo, ref=sha, path=path))
    return plugin_map(json.loads(text), repo)


def codex_descriptions(
    session: requests.Session, names: list[str], token: str | None = None
) -> dict[str, str]:
    """Codex's marketplace.json has no descriptions; each plugin's manifest does."""
    out = {}
    for name in names[:10]:
        url = RAW.format(
            repo="openai/plugins", ref="HEAD", path=f"plugins/{name}/.codex-plugin/plugin.json"
        )
        try:
            data = json.loads(get_text(session, url, retries=0))
        except Exception:  # noqa: BLE001 - a description is optional
            continue
        iface = data.get("interface") or {}
        text = iface.get("shortDescription") or data.get("description") or ""
        out[name] = " ".join(str(text).split())[:200]
    return out


_KIMI_CARD = re.compile(r"__pluginCard\b(.*?)(?=__pluginCard\b|$)", re.S)
_TAG_TEXT = re.compile(r"<(h3|p)\b[^>]*>([^<]*)</\1>")


def parse_kimi(html: str) -> dict[str, dict[str, Any]]:
    out = {}
    for block in _KIMI_CARD.findall(html):
        texts = {}
        for tag, text in _TAG_TEXT.findall(block):
            texts.setdefault(tag, text.strip())
        if texts.get("h3"):
            out[texts["h3"]] = {"description": texts.get("p", "")}
    if not out:
        raise ValueError("no plugin cards found on the Kimi page")
    return out


def fetch_kimi(session: requests.Session, storage: Storage, day: str) -> dict[str, Any]:
    observed = utc_now()
    html = get_text(session, KIMI_URL)
    return {
        "source": "catalog-kimi",
        "day": day,
        "origin": "live",
        "observed_at": iso(observed),
        "label": "Kimi 插件介绍页",
        "plugins": parse_kimi(html),
        "raw": [storage.save_raw(day, "kimi-plugins.html", html)],
    }


def fetch_claude_stats(session: requests.Session, storage: Storage, day: str) -> dict[str, Any]:
    observed = utc_now()
    text = get_text(session, CLAUDE_STATS_URL)
    data = json.loads(text)
    installs = {}
    for key, entry in (data.get("plugins") or {}).items():
        value = entry.get("unique_installs")
        if isinstance(value, int):
            installs[key.split("@")[0]] = value
    generated = data.get("generated_at")
    return {
        "source": "claude-installs",
        "day": day,
        "origin": "live",
        "observed_at": iso(observed),
        "generated_at": generated,
        "age_days": (observed - parse_iso(generated)).days if generated else None,
        "installs": installs,
        "raw": [storage.save_raw(day, "claude-plugin-details.json", text)],
    }
