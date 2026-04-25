from __future__ import annotations

from ..models import Source
from .aggregations.github_trending import source as github_trending_source
from .aggregations.hf_papers import source as hf_papers_source
from .aggregations.hn import source as hn_source
from .aggregations.lobsters import source as lobsters_source
from .aggregations.product_hunt import source as product_hunt_source
from .aggregations.skills_sh import source_hot as skills_sh_hot_source
from .aggregations.skills_sh import source_trending as skills_sh_trending_source
from .blogs.ahead_of_ai import source as ahead_of_ai_source
from .blogs.alignment_anthropic import source as alignment_anthropic_source
from .blogs.alphasignal_last_email import source as alphasignal_last_email_source
from .blogs.anthropic_youtube import source as anthropic_youtube_source
from .blogs.antirez import source as antirez_source
from .blogs.arxiv_cs_ai import source as arxiv_cs_ai_source
from .blogs.ben_evans import source as ben_evans_source
from .blogs.claude_blog import source as claude_blog_source
from .blogs.cognitive_revolution import source as cognitive_revolution_source
from .blogs.crunchbase_news import source as crunchbase_news_source
from .blogs.dwarkesh_blog import source as dwarkesh_blog_source
from .blogs.dwarkesh_podcast import source as dwarkesh_podcast_source
from .blogs.founders_fund_anatomy import source as founders_fund_source
from .blogs.fs_blog import source as fs_blog_source
from .blogs.globenewswire_earnings import source as globenewswire_earnings_source
from .blogs.gwern_changelog import source as gwern_changelog_source
from .blogs.hard_fork import source as hard_fork_source
from .blogs.hf_blog import source as hf_blog_source
from .blogs.huyen_chip import source as huyen_chip_source
from .blogs.import_ai import source as import_ai_source
from .blogs.interconnects import source as interconnects_source
from .blogs.last_week_in_ai import source as last_week_in_ai_source
from .blogs.latent_space import source as latent_space_source
from .blogs.lennys_newsletter import source as lennys_newsletter_source
from .blogs.lilian_weng import source as lilian_weng_source
from .blogs.lucumr import source as lucumr_source
from .blogs.mailchimp_archive import source as mailchimp_archive_source
from .blogs.ml_street_talk import source as ml_street_talk_source
from .blogs.no_priors import source as no_priors_source
from .blogs.onboard import source as onboard_source
from .blogs.openai_dev_blog import source as openai_dev_blog_source
from .blogs.openai_news import source as openai_news_source
from .blogs.paul_graham import source as paul_graham_source
from .blogs.pragmatic_engineer import source as pragmatic_engineer_source
from .blogs.ramp_builders import source as ramp_builders_source
from .blogs.sec_edgar_form_d import source as sec_edgar_form_d_source
from .blogs.semianalysis import source as semianalysis_source
from .blogs.sharp_tech import source as sharp_tech_source
from .blogs.sifted import source as sifted_source
from .blogs.simon_willison import source as simon_willison_source
from .blogs.sorrycc import source as sorrycc_source
from .blogs.stratechery import source as stratechery_source
from .blogs.sv101 import source as sv101_source
from .blogs.techcrunch_fundings import source as techcrunch_fundings_source
from .blogs.techcrunch_venture import source as techcrunch_venture_source
from .blogs.techmeme import source as techmeme_source
from .blogs.the_batch import source as the_batch_source
from .blogs.the_information import source as the_information_source
from .blogs.training_data import source as training_data_source
from .blogs.trends_vc import source as trends_vc_source
from .blogs.twenty_vc import source as twenty_vc_source
from .blogs.unsupervised_learning import source as unsupervised_learning_source
from .blogs.vercel_blog import source as vercel_blog_source
from .blogs.yc_oss import source as yc_oss_source
from .blogs.zero_one_me import source as zero_one_me_source
from .blogs.zhang_xiaojun import source as zhang_xiaojun_source

_SOURCES: list[Source] = [
    hn_source(),
    lobsters_source(),
    # releasebot: disabled — releasebot.io SSL unreachable, JSON structure changed
    hf_papers_source(),
    github_trending_source(),
    product_hunt_source(),
    skills_sh_trending_source(),
    skills_sh_hot_source(),
    zero_one_me_source(),
    antirez_source(),
    ben_evans_source(),
    founders_fund_source(),
    fs_blog_source(),
    claude_blog_source(),
    gwern_changelog_source(),
    hf_blog_source(),
    huyen_chip_source(),
    latent_space_source(),
    lilian_weng_source(),
    lucumr_source(),
    openai_dev_blog_source(),
    openai_news_source(),
    paul_graham_source(),
    pragmatic_engineer_source(),
    ramp_builders_source(),
    semianalysis_source(),
    simon_willison_source(),
    sorrycc_source(),
    stratechery_source(),
    the_information_source(),
    trends_vc_source(),
    lennys_newsletter_source(),
    mailchimp_archive_source(),
    crunchbase_news_source(),
    techmeme_source(),
    vercel_blog_source(),
    alphasignal_last_email_source(),
    # ainews-smol: disabled — news.smol.ai returned 404, service shut down
    globenewswire_earnings_source(),
    no_priors_source(),
    hard_fork_source(),
    dwarkesh_podcast_source(),
    dwarkesh_blog_source(),
    cognitive_revolution_source(),
    ml_street_talk_source(),
    training_data_source(),
    unsupervised_learning_source(),
    twenty_vc_source(),
    sharp_tech_source(),
    zhang_xiaojun_source(),
    onboard_source(),
    sv101_source(),
    interconnects_source(),
    import_ai_source(),
    ahead_of_ai_source(),
    last_week_in_ai_source(),
    alignment_anthropic_source(),
    anthropic_youtube_source(),
    arxiv_cs_ai_source(),
    the_batch_source(),
    techcrunch_venture_source(),
    techcrunch_fundings_source(),
    sifted_source(),
    yc_oss_source(),
    sec_edgar_form_d_source(),
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
