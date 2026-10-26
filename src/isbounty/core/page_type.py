"""Page-type classification.

Page type is established before payment. A third-party article and an
official disclosure policy are not the same kind of input.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from .fetcher import host_matches
from .models import PageContent, PageTypeResult
from .platforms import resolve_platform

PROGRAM_TYPES = {"official_program", "closed_program"}
NON_PROGRAM_TYPES = {
    "news", "blog", "wiki", "directory", "aggregator", "marketing",
    "generic_security",
}

_PROGRAM_TITLE = re.compile(
    r"vulnerability disclosure (?:policy|program|programme)|"
    r"bug bounty (?:program|programme|policy)|responsible disclosure|"
    r"security (?:policy|bug bounty)|report a vulnerability|"
    r"defect and vulnerability disclosure|vulnerability reward program",
    re.IGNORECASE,
)
_PROGRAM_PATH = re.compile(
    r"security|security-policy|vulnerability-disclosure|vulnerability-reporting|"
    r"bug-bounty|responsible-disclosure|vdp|report-a-vulnerability|"
    r"report-vulnerability|vulnerability",
    re.IGNORECASE,
)
_INVITATION = re.compile(
    r"(?:please |you can |you may )?(?:report|submit|send|disclose)\s+"
    r"(?:a |your |any |the )?(?:security )?(?:vulnerabilit\w*|bug|issue|finding|report)"
    r"|if you (?:believe|think) you (?:have )?found",
    re.IGNORECASE,
)
_SCOPE = re.compile(
    r"\b(?:in scope|out of scope|scope|eligib\w*|rules|safe harbou?r|"
    r"authorized (?:research|testing))\b",
    re.IGNORECASE,
)
_CHANNEL = re.compile(
    r"\b(?:security|psirt|vulnerabilit(?:y|ies))@[\w-]+(?:\.[\w-]+)+|"
    r"submit (?:a |your |the )?(?:vulnerability|report|bug)|"
    r"report (?:a |the )?vulnerabilit|hackerone\.com/|bugcrowd\.com/|"
    r"intigriti\.com/|security\.txt",
    re.IGNORECASE,
)
_NON_PROGRAM_TITLE = re.compile(
    r"what is a bug bounty|bug bounty vs vdp|top bug bounty|best bug bounty|"
    r"list of bug bounty|browse programs|compare programs|find a program|"
    r"view all programs|start a bug bounty|bug bounty platforms?|"
    r"how to (?:start|run) a bug bounty",
    re.IGNORECASE,
)
_CLOSED = re.compile(
    r"program (?:has )?ended|program (?:is )?closed|no longer accepting reports|"
    r"no longer accept reports|we no longer accept reports|closed program",
    re.IGNORECASE,
)
_STILL_ACCEPTS = re.compile(
    r"still (?:accept|accepting|welcome)|continue(?:s)? to accept|"
    r"are (?:still )?accepted|accepting reports|reports are welcome", re.IGNORECASE,
)
_ARTICLE_STRUCTURE = re.compile(
    r"\b(?:wiki|article|author|published|citation needed|read more|"
    r"related articles|references)\b", re.IGNORECASE,
)


def _meta(page: PageContent, key: str) -> str:
    return str((page.metadata or {}).get(key) or "")


def _title_text(page: PageContent) -> str:
    return " ".join(filter(None, [
        _meta(page, "title"), _meta(page, "og_title"), _meta(page, "og:title"),
        " ".join(page.headings[:3]),
    ]))


def _deny_category(page: PageContent, denylist: dict[str, list[str]]) -> Optional[str]:
    host = (page.host or "").lower()
    for category, entries in denylist.items():
        if any(host_matches(host, entry) for entry in entries):
            return category
    return None


def _non_program_path(page: PageContent, category: Optional[str]) -> Optional[str]:
    path = (page.final_url or page.url or "").lower()
    if category in ("news", "blog") and re.search(
        r"/(?:news|blog|article|wiki|directory|programs?)(?:/|$)", path
    ):
        return category
    return None


def _is_article_metadata(page: PageContent) -> bool:
    return str(_meta(page, "og_type")).lower() == "article"


def classify_page(page: PageContent,
                  denylist: Optional[dict[str, list[str]]] = None,
                  http_post: Optional[Callable] = None) -> PageTypeResult:
    denylist = denylist or {}

    platform = resolve_platform(page, http_post=http_post)
    if platform is not None:
        return platform

    category = _deny_category(page, denylist)
    if category:
        return PageTypeResult(
            category, 0.9, [f"host matches {category} denylist entry"],
        )
    path_category = _non_program_path(page, category)
    if path_category:
        return PageTypeResult(
            path_category, 0.8, [f"path matches {path_category} pattern"],
        )

    text = page.raw_text or ""
    title = _title_text(page)
    path = (page.final_url or page.url or "")
    lower = text.lower()

    if _CLOSED.search(text) and _STILL_ACCEPTS.search(text):
        return PageTypeResult(
            "official_program", 0.7,
            ["closed bounty but vulnerability reports are still accepted"],
        )
    if _CLOSED.search(text):
        return PageTypeResult(
            "closed_program", 0.8, ["explicit closure language without a current channel"],
        )

    if _NON_PROGRAM_TITLE.search(title) or _NON_PROGRAM_TITLE.search(text[:1500]):
        return PageTypeResult(
            "directory", 0.85, ["title/body lists or explains programs generally"],
        )

    if _is_article_metadata(page) and not (
        _PROGRAM_TITLE.search(title) or _PROGRAM_PATH.search(path)
    ):
        return PageTypeResult(
            "news", 0.65, ["article metadata without program title or path"],
        )

    has_title = bool(_PROGRAM_TITLE.search(title))
    has_path = bool(_PROGRAM_PATH.search(path))
    has_invitation = bool(_INVITATION.search(text))
    has_scope = bool(_SCOPE.search(text))
    has_channel = bool(_CHANNEL.search(text))
    self_reference = bool(
        page.domain and page.domain.lower() in lower
    ) or bool(_CHANNEL.search(text))

    signals: list[str] = []
    if has_path:
        signals.append("program-like URL path")
    if has_title:
        signals.append("program title or heading")
    if has_invitation:
        signals.append("vulnerability reporting invitation")
    if has_scope:
        signals.append("scope, rules or eligibility language")
    if has_channel:
        signals.append("security-specific reporting channel")
    if self_reference:
        signals.append("self-reference or own-domain reporting")

    score = sum([has_path, has_title, has_invitation, has_scope,
                 has_channel, self_reference])
    strong = has_title or has_invitation or has_scope

    if score >= 2 and strong:
        return PageTypeResult(
            "official_program", min(0.55 + 0.08 * score, 0.95), signals,
        )

    generic_contact = bool(re.search(
        r"\bcontact (?:us|security)\b|\bsecurity contact\b", title + " " + text[:800],
        re.IGNORECASE,
    ))
    if generic_contact and not strong:
        return PageTypeResult(
            "generic_security", 0.6, ["security contact page without program scope"],
        )

    if _ARTICLE_STRUCTURE.search(text[:4000]) and not strong:
        return PageTypeResult(
            "unknown", 0.4, ["article-like page without clear program evidence"],
        )

    return PageTypeResult(
        "unknown", 0.35, signals + ["not enough evidence to establish page type"],
    )
