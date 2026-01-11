from __future__ import annotations

from .index_models import IndexSource

INDEX_SOURCES: dict[str, IndexSource] = {
    "hn": IndexSource(
        slug="hn",
        name="Hacker News",
        homepage_url="https://news.ycombinator.com/",
    ),
    "lobsters": IndexSource(
        slug="lobsters",
        name="Lobsters",
        homepage_url="https://lobste.rs/",
    ),
    "releasebot": IndexSource(
        slug="releasebot",
        name="Releasebot",
        homepage_url="https://releasebot.io/",
    ),
    "hf-papers": IndexSource(
        slug="hf-papers",
        name="Hugging Face Papers",
        homepage_url="https://huggingface.co/papers",
    ),
    "github-trending": IndexSource(
        slug="github-trending",
        name="GitHub Trending",
        homepage_url="https://github.com/trending",
    ),
    "product-hunt-rss": IndexSource(
        slug="product-hunt-rss",
        name="Product Hunt",
        homepage_url="https://www.producthunt.com/",
    ),
}


def list_index_sources() -> list[IndexSource]:
    return list(INDEX_SOURCES.values())


def index_slugs() -> list[str]:
    return list(INDEX_SOURCES.keys())
