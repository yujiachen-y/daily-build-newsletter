from __future__ import annotations

from ...errors import FetchError
from ...http import get_json
from ...models import BlogItem, FetchContext, Source

YC_OSS_URL = "https://yc-oss.github.io/api/companies/all.json"


def source() -> Source:
    return Source(
        id="yc-oss",
        name="YC Companies (yc-oss)",
        kind="blog",
        method="api",
        fetch=fetch_yc_oss,
    )


def fetch_yc_oss(ctx: FetchContext) -> list[BlogItem]:
    """Fetch YC companies from the yc-oss open API and return recent ones."""
    payload = get_json(ctx.session, YC_OSS_URL, timeout=30)
    if not isinstance(payload, list):
        raise FetchError("yc-oss payload is not a list")

    # Determine the latest batch code(s) to surface new companies.
    # Batch codes look like "Winter 2026", "Summer 2025", etc.
    current_year = ctx.now.year
    recent_batches = {
        f"{season} {year}"
        for year in (current_year, current_year - 1)
        for season in ("Winter", "Spring", "Summer", "Fall")
    }

    items: list[BlogItem] = []
    for company in payload:
        batch = company.get("batch", "")
        if batch not in recent_batches:
            continue

        name = company.get("name", "")
        url = company.get("url") or company.get("website") or ""
        if not name or not url:
            continue

        one_liner = company.get("one_liner", "")
        description = company.get("long_description") or company.get("description") or ""
        team_size = company.get("team_size", "")
        tags = company.get("tags") or []
        status = company.get("status", "")

        summary_parts = []
        if one_liner:
            summary_parts.append(one_liner)
        if batch:
            summary_parts.append(f"Batch: {batch}")
        if team_size:
            summary_parts.append(f"Team size: {team_size}")
        if status:
            summary_parts.append(f"Status: {status}")
        if tags:
            summary_parts.append(f"Tags: {', '.join(tags[:5])}")

        content_parts = []
        if description:
            content_parts.append(description)
        if one_liner and description != one_liner:
            content_parts.insert(0, f"**{one_liner}**\n")

        items.append(
            BlogItem(
                title=f"{name} ({batch})" if batch else name,
                url=url,
                published_at=None,
                author=None,
                summary=" | ".join(summary_parts) if summary_parts else None,
                content_markdown="\n\n".join(content_parts) if content_parts else None,
            )
        )

    if not items:
        raise FetchError("yc-oss: no companies found for recent batches")
    return items
