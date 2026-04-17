from __future__ import annotations

from datetime import timedelta

from ...errors import FetchError
from ...http import get_json
from ...models import BlogItem, FetchContext, Source

# SEC EDGAR full-text search API for Form D filings (private placements).
# Free, no API key required. Returns recent filings in JSON.
_EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"


def source() -> Source:
    return Source(
        id="sec-edgar-form-d",
        name="SEC EDGAR Form D",
        kind="blog",
        method="api",
        fetch=fetch_form_d,
    )


def fetch_form_d(ctx: FetchContext) -> list[BlogItem]:
    """Fetch recent Form D filings from SEC EDGAR full-text search."""
    end = ctx.now.strftime("%Y-%m-%d")
    start = (ctx.now - timedelta(days=3)).strftime("%Y-%m-%d")

    url = (
        f"https://efts.sec.gov/LATEST/search-index"
        f"?q=%22Form+D%22&forms=D&dateRange=custom"
        f"&startdt={start}&enddt={end}"
    )
    payload = get_json(ctx.session, url, timeout=30)

    hits = payload.get("hits", {}).get("hits", [])
    if not hits:
        return []  # No filings in date range (common on weekends)

    items: list[BlogItem] = []
    for hit in hits[:50]:
        src = hit.get("_source", {})
        display_names = src.get("display_names") or ["Unknown"]
        entity_name = display_names[0]
        file_date = src.get("file_date", "")
        file_num = src.get("file_num", "")
        form_type = src.get("form_type", "D")

        if not file_num:
            continue
        filing_url = (
            "https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcompany&filenum={file_num}"
            "&type=D&dateb=&owner=include&count=10&action=getcompany"
        )

        items.append(
            BlogItem(
                title=f"{entity_name} — Form {form_type}",
                url=filing_url,
                published_at=file_date,
                author=None,
                summary=f"SEC Form D filing by {entity_name} on {file_date}",
                content_markdown=None,
            )
        )

    if not items:
        raise FetchError("SEC EDGAR Form D: no items after processing")
    return items
