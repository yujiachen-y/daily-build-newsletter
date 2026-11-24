"""GitHub repo stats used as an outside check on install counters.

A skill whose repo has 3 stars but 29,000 installs in a day is far more likely to be install
farming than a breakout, so stars and repo age are looked up for every repo a signal names.
"""

from __future__ import annotations

import re
from typing import Any

import requests

from .http import FetchError, request

GRAPHQL = "https://api.github.com/graphql"
REST = "https://api.github.com/repos/{repo}"
BATCH = 50
REST_LIMIT = 40  # unauthenticated REST allows 60 requests an hour
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _query(repos: list[str]) -> str:
    parts = []
    for i, repo in enumerate(repos):
        owner, name = repo.split("/", 1)
        parts.append(
            f'r{i}: repository(owner: "{_esc(owner)}", name: "{_esc(name)}") '
            "{ nameWithOwner stargazerCount createdAt isFork isArchived }"
        )
    return "query {\n" + "\n".join(parts) + "\n}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace('"', "")


def repo_stats(
    session: requests.Session, repos: list[str], token: str | None
) -> dict[str, dict[str, Any] | None]:
    """{owner/repo (lower-case): {stars, created, fork, archived}} or None when not found.

    Without a token only the first REST_LIMIT repos (in the given priority order) are looked up.
    """
    wanted = list(dict.fromkeys(r.strip("/") for r in repos if r and _REPO_RE.match(r)))
    out: dict[str, dict[str, Any] | None] = {}
    if token:
        for start in range(0, len(wanted), BATCH):
            chunk = wanted[start : start + BATCH]
            response = request(
                session,
                "POST",
                GRAPHQL,
                json={"query": _query(chunk)},
                headers={"Authorization": f"Bearer {token}"},
            )
            data = (response.json() or {}).get("data") or {}
            for i, repo in enumerate(chunk):
                node = data.get(f"r{i}")
                out[repo.lower()] = _node(node) if node else None
        return out
    for repo in wanted[:REST_LIMIT]:
        try:
            node = request(session, "GET", REST.format(repo=repo), retries=0).json()
        except FetchError:
            out[repo.lower()] = None
            continue
        out[repo.lower()] = {
            "stars": node.get("stargazers_count"),
            "created": (node.get("created_at") or "")[:10] or None,
            "fork": bool(node.get("fork")),
            "archived": bool(node.get("archived")),
        }
    return out


def _node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "stars": node.get("stargazerCount"),
        "created": (node.get("createdAt") or "")[:10] or None,
        "fork": bool(node.get("isFork")),
        "archived": bool(node.get("isArchived")),
    }
