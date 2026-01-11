from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from .extract import extract_markdown
from .models import ItemCandidate, SourcePolicy
from .text_processing import detect_blocked_text


class Throttle:
    def __init__(self, policy: SourcePolicy) -> None:
        self.policy = policy
        self.last_request_at: float | None = None
        self._lock = None

    def wait(self) -> None:
        if self._lock is None:
            import threading

            self._lock = threading.Lock()
        intervals: list[float] = []
        if self.policy.max_rpm:
            intervals.append(60.0 / float(self.policy.max_rpm))
        if self.policy.min_interval_sec:
            intervals.append(float(self.policy.min_interval_sec))
        min_interval = max(intervals) if intervals else 0.0
        if min_interval <= 0:
            return
        delay = 0.0
        with self._lock:
            now = time.time()
            if self.last_request_at is None:
                self.last_request_at = now
                return
            target = self.last_request_at + min_interval
            if now < target:
                delay = target - now
                if self.policy.jitter_sec:
                    delay += self.policy.jitter_sec
                self.last_request_at = now + delay
            else:
                self.last_request_at = now
        if delay > 0:
            time.sleep(delay)


@dataclass
class ErrorInfo:
    stage: str
    code: str
    message: str
    url: str | None


@dataclass
class FetchJob:
    candidate: ItemCandidate
    item_id: int
    item_key: str


@dataclass
class FetchOutcome:
    job: FetchJob
    raw_markdown: str | None
    comments_markdown: str
    comments_count: int
    error: ErrorInfo | None = None
    comments_error: ErrorInfo | None = None


def build_session(user_agent: str | None) -> requests.Session:
    session = requests.Session()
    if user_agent:
        session.headers["User-Agent"] = user_agent
    return session


def fetch_candidate(
    adapter: Any,
    job: FetchJob,
    config: dict[str, Any],
    throttle: Throttle,
    user_agent: str | None,
) -> FetchOutcome:
    session = build_session(user_agent)
    try:
        throttle.wait()
        html = adapter.fetch_detail(job.candidate, session)
    except Exception as exc:
        return FetchOutcome(
            job=job,
            raw_markdown=None,
            comments_markdown="",
            comments_count=0,
            error=ErrorInfo(
                stage="detail",
                code="detail",
                message=str(exc),
                url=job.candidate.detail_url,
            ),
        )

    try:
        raw_markdown = extract_markdown(html)
    except Exception as exc:
        return FetchOutcome(
            job=job,
            raw_markdown=None,
            comments_markdown="",
            comments_count=0,
            error=ErrorInfo(
                stage="detail",
                code="extract",
                message=str(exc),
                url=job.candidate.detail_url,
            ),
        )
    blocked = detect_blocked_text(raw_markdown)
    if blocked:
        return FetchOutcome(
            job=job,
            raw_markdown=None,
            comments_markdown="",
            comments_count=0,
            error=ErrorInfo(
                stage="detail",
                code="blocked",
                message=f"Blocked content detected: {blocked}",
                url=job.candidate.detail_url,
            ),
        )

    comments_markdown = ""
    comments_count = 0
    comments_error = None
    fetch_comments: Callable[..., tuple[str, int]] | None = getattr(adapter, "fetch_comments", None)
    if fetch_comments:
        try:
            throttle.wait()
            comments_markdown, comments_count = fetch_comments(
                job.candidate,
                session,
                limit=config.get("top_comments_limit"),
            )
        except Exception as exc:
            comments_error = ErrorInfo(
                stage="comments",
                code="comments",
                message=str(exc),
                url=job.candidate.comment_url or job.candidate.detail_url,
            )
            comments_markdown = ""
            comments_count = 0
        else:
            blocked = detect_blocked_text(comments_markdown)
            if blocked:
                comments_error = ErrorInfo(
                    stage="comments",
                    code="blocked",
                    message=f"Blocked content detected: {blocked}",
                    url=job.candidate.comment_url or job.candidate.detail_url,
                )
                comments_markdown = ""
                comments_count = 0

    return FetchOutcome(
        job=job,
        raw_markdown=raw_markdown,
        comments_markdown=comments_markdown,
        comments_count=comments_count,
        comments_error=comments_error,
    )
