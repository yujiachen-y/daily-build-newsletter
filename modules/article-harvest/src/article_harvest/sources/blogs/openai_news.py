from __future__ import annotations

from ..rss import make_rss_source

OPENAI_NEWS_RSS_URL = "https://openai.com/news/rss.xml"


def source():
    return make_rss_source("openai-news", "OpenAI News", OPENAI_NEWS_RSS_URL)
