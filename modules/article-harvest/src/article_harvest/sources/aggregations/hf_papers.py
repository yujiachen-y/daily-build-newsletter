from __future__ import annotations

from ...errors import FetchError
from ...http import get_json
from ...models import AggregationItem, FetchContext, Source

HF_PAPERS_URL = "https://huggingface.co/api/daily_papers"
HF_PAPERS_LIMIT = 15


def source() -> Source:
    return Source(
        id="hf-papers",
        name="Hugging Face Papers",
        kind="aggregation",
        method="api",
        fetch=fetch_hf_papers,
    )


def fetch_hf_papers(ctx: FetchContext) -> list[AggregationItem]:
    payload = get_json(ctx.session, HF_PAPERS_URL)
    if not isinstance(payload, list):
        raise FetchError("HF papers payload invalid")
    items: list[AggregationItem] = []
    for rank, entry in enumerate(payload[:HF_PAPERS_LIMIT], start=1):
        if not isinstance(entry, dict):
            continue
        paper = entry.get("paper") or {}
        title = entry.get("title") or paper.get("title")
        if not title:
            continue
        paper_id = paper.get("id")
        url = None
        if paper_id:
            url = f"https://huggingface.co/papers/{paper_id}"
        url = url or paper.get("projectPage") or paper.get("project_page")
        if not url:
            continue
        authors = paper.get("authors") or []
        author = None
        if authors:
            first = authors[0]
            author = first.get("name") if isinstance(first, dict) else None
        items.append(
            AggregationItem(
                title=title,
                url=url,
                published_at=entry.get("publishedAt") or paper.get("publishedAt"),
                author=author,
                score=paper.get("upvotes"),
                comments_count=entry.get("numComments"),
                rank=rank,
                discussion_url=None,
                extra={},
            )
        )
    if not items:
        raise FetchError("HF papers list empty")
    return items
