from __future__ import annotations

from ..models import Source
from .aggregations.hn import source as hn_source
from .aggregations.lobsters import source as lobsters_source
from .aggregations.releasebot import source as releasebot_source
from .aggregations.hf_papers import source as hf_papers_source
from .aggregations.github_trending import source as github_trending_source
from .aggregations.product_hunt import source as product_hunt_source
from .blogs.zero_one_me import source as zero_one_me_source
from .blogs.antirez import source as antirez_source
from .blogs.ben_evans import source as ben_evans_source
from .blogs.founders_fund_anatomy import source as founders_fund_source
from .blogs.fs_blog import source as fs_blog_source
from .blogs.gwern_changelog import source as gwern_changelog_source
from .blogs.hf_blog import source as hf_blog_source
from .blogs.huyen_chip import source as huyen_chip_source
from .blogs.latent_space import source as latent_space_source
from .blogs.lilian_weng import source as lilian_weng_source
from .blogs.lucumr import source as lucumr_source
from .blogs.paul_graham import source as paul_graham_source
from .blogs.pragmatic_engineer import source as pragmatic_engineer_source
from .blogs.simon_willison import source as simon_willison_source
from .blogs.sorrycc import source as sorrycc_source
from .blogs.stratechery import source as stratechery_source
from .blogs.trends_vc import source as trends_vc_source
from .blogs.lennys_newsletter import source as lennys_newsletter_source
from .blogs.mailchimp_archive import source as mailchimp_archive_source
from .blogs.crunchbase_news import source as crunchbase_news_source
from .blogs.techmeme import source as techmeme_source
from .blogs.alphasignal_last_email import source as alphasignal_last_email_source


_SOURCES: list[Source] = [
    hn_source(),
    lobsters_source(),
    releasebot_source(),
    hf_papers_source(),
    github_trending_source(),
    product_hunt_source(),
    zero_one_me_source(),
    antirez_source(),
    ben_evans_source(),
    founders_fund_source(),
    fs_blog_source(),
    gwern_changelog_source(),
    hf_blog_source(),
    huyen_chip_source(),
    latent_space_source(),
    lilian_weng_source(),
    lucumr_source(),
    paul_graham_source(),
    pragmatic_engineer_source(),
    simon_willison_source(),
    sorrycc_source(),
    stratechery_source(),
    trends_vc_source(),
    lennys_newsletter_source(),
    mailchimp_archive_source(),
    crunchbase_news_source(),
    techmeme_source(),
    alphasignal_last_email_source(),
]


def list_sources(include_disabled: bool = True) -> list[Source]:
    if include_disabled:
        return list(_SOURCES)
    return [source for source in _SOURCES if source.enabled]


def get_source(source_id: str) -> Source:
    for source in _SOURCES:
        if source.id == source_id:
            return source
    raise KeyError(f"Unknown source: {source_id}")
