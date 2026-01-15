from __future__ import annotations

import json
import subprocess
import time
from html import unescape

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ...errors import FetchError
from ...models import BlogItem, FetchContext, Source

LAST_EMAIL_URL = "https://alphasignal.ai/last-email"


def source() -> Source:
    return Source(
        id="alphasignal-last-email",
        name="AlphaSignal Last Email",
        kind="blog",
        method="agent",
        fetch=fetch_last_email,
    )


def fetch_last_email(ctx: FetchContext) -> list[BlogItem]:
    iframe_html = _fetch_iframe_srcdoc(ctx)
    content_html, title = _extract_email_html(iframe_html)
    normalized_html = _normalize_email_html(content_html)
    content_markdown = _cleanup_markdown(md(normalized_html)) if normalized_html else ""
    published_at = ctx.now.date().isoformat()
    url = f"{LAST_EMAIL_URL}?issue={published_at}"
    return [
        BlogItem(
            title=title or "AlphaSignal Last Email",
            url=url,
            published_at=published_at,
            content_markdown=content_markdown,
        )
    ]


def _fetch_iframe_srcdoc(ctx: FetchContext) -> str:
    session = f"alphasignal-{ctx.run_id}"
    _run_agent_browser(["open", LAST_EMAIL_URL], session)
    _run_agent_browser(["wait", "2000"], session)
    time.sleep(0.2)
    payload = _run_agent_browser(
        [
            "eval",
            "(() => { const iframe = document.querySelector('iframe'); "
            "return iframe ? { srcdoc: iframe.getAttribute('srcdoc') } : null; })()",
        ],
        session,
    )
    _run_agent_browser(["close"], session)
    if not isinstance(payload, dict):
        raise FetchError("AlphaSignal agent output invalid")
    srcdoc = payload.get("srcdoc")
    if not srcdoc:
        raise FetchError("AlphaSignal iframe srcdoc missing")
    return unescape(str(srcdoc))


def _extract_email_html(iframe_html: str) -> tuple[str, str | None]:
    soup = BeautifulSoup(iframe_html, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    body = soup.body
    if body:
        return str(body), title
    return iframe_html, title


def _normalize_email_html(content_html: str) -> str:
    soup = BeautifulSoup(content_html, "lxml")
    for tag in soup.find_all(["script", "style", "noscript", "meta", "head"]):
        tag.decompose()
    for tag in soup.find_all(style=True):
        style = tag.get("style", "").lower()
        if "display:none" in style or "visibility:hidden" in style or "max-height:0" in style:
            tag.decompose()
    for img in soup.find_all("img"):
        img.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(["table", "tbody", "tr", "td"]):
        tag.insert_before("\n")
        tag.insert_after("\n")
        tag.unwrap()
    return str(soup.body or soup)


def _cleanup_markdown(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned: list[str] = []
    for line in lines:
        if _is_table_rule(line) or _is_pipe_separator(line):
            continue
        cleaned.append(line)
    trimmed = _trim_preamble(cleaned)
    return _collapse_blank_lines(trimmed)


def _is_table_rule(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") > 4:
        return True
    return False


def _is_pipe_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("|") and stripped.endswith("|"):
        return stripped.replace("|", "").strip() == ""
    return False


def _trim_preamble(lines: list[str]) -> list[str]:
    for idx, line in enumerate(lines):
        lowered = line.lower()
        if lowered.startswith("hey ") or lowered.startswith("your daily briefing"):
            return lines[idx:]
    return lines


def _collapse_blank_lines(lines: list[str]) -> str:
    output: list[str] = []
    blank = False
    for line in lines:
        if line.strip():
            blank = False
            output.append(line)
            continue
        if not blank:
            output.append("")
        blank = True
    return "\n".join(output).strip()


def _run_agent_browser(args: list[str], session: str) -> dict | None:
    cmd = ["agent-browser", "--session", session, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FetchError(f"agent-browser failed: {proc.stderr.strip() or proc.stdout.strip()}")
    output = proc.stdout.strip()
    if not output:
        return None
    return _parse_json_output(output)


def _parse_json_output(output: str) -> dict | None:
    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(output[start : end + 1])
    except json.JSONDecodeError:
        return None
