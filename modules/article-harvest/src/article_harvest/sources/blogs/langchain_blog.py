from __future__ import annotations

from ..rss import make_rss_source


def source():
    return make_rss_source(
        "langchain-blog",
        "LangChain Blog",
        "https://www.langchain.com/blog/rss.xml",
    )
