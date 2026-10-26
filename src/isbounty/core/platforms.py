"""Platform resolvers.

These are authoritative for specific program URLs. They bypass pronoun and
first-party scoring requirements. They fail closed to needs_review or
insufficient_content, never to a guessed label.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional
from urllib.parse import urlparse

from .models import PageContent, PageTypeResult

_HACKERONE_RESERVED = {
    "", "bug-bounty-programs", "blog", "customers", "product", "products",
    "resources", "events", "about", "careers", "press", "legal", "terms",
    "privacy", "leaderboard", "hacktivity", "opportunities", "support",
}
_HACKERONE_DIRECTORY = {
    "bug-bounty-programs", "opportunities", "hacktivity", "leaderboard",
}
_BUGCROWD_DIRECTORY = {"", "engagements", "programs", "customers", "blog",
                       "resources", "about", "careers", "press", "legal"}
_INTIGRITI_DIRECTORY = {"", "programs", "blog", "resources", "about",
                        "careers", "press", "legal", "company", "researcher"}


def _segments(url: str) -> list[str]:
    return [s for s in urlparse(url or "").path.split("/") if s]


def _host(page: PageContent) -> str:
    return (page.host or urlparse(page.final_url or page.url).hostname or "").lower()


def _title(page: PageContent) -> str:
    meta = page.metadata or {}
    parts = [
        str(meta.get("title") or ""),
        str(meta.get("og_title") or ""),
        str(meta.get("og:title") or ""),
        " ".join(page.headings[:2]),
    ]
    return " ".join(p for p in parts if p).strip()


def _description(page: PageContent) -> str:
    meta = page.metadata or {}
    return " ".join(
        str(meta.get(k) or "") for k in ("description", "og_description", "og:description")
    ).strip()


def _host_is(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _call_json(http_post: Optional[Callable], url: str, payload: dict,
               timeout: int = 10) -> Optional[dict]:
    if http_post is None:
        return None
    try:
        result = http_post(url, json=payload, timeout=timeout)
    except Exception:  # noqa: BLE001 - resolver is optional infrastructure
        return None
    if isinstance(result, dict):
        return result
    try:
        return result.json()
    except Exception:  # noqa: BLE001
        return None


def _embedded_json(page: PageContent) -> dict:
    if (page.metadata or {}).get("platform_data"):
        return dict(page.metadata["platform_data"])
    html = page.raw_html or page.raw_text or ""
    data: dict = {}
    for key in ("rewardAllocation", "name", "code", "state"):
        match = re.search(r'"%s"\s*:\s*"([^"]*)"' % key, html)
        if match:
            data[key] = match.group(1)
    return data


def _hackerone(page: PageContent, http_post: Optional[Callable]) -> Optional[PageTypeResult]:
    host = _host(page)
    if not _host_is(host, "hackerone.com"):
        return None
    parts = _segments(page.final_url or page.url)
    first = parts[0].lower() if parts else ""
    if not parts:
        return PageTypeResult("marketing", 0.9, ["platform homepage"], "hackerone")
    if first == "blog":
        return PageTypeResult("blog", 0.95, ["hackerone blog path"], "hackerone")
    if first in _HACKERONE_RESERVED:
        kind = "directory" if first in _HACKERONE_DIRECTORY else "marketing"
        return PageTypeResult(kind, 0.9, [f"reserved hackerone path '/{first}'"], "hackerone")

    handle = first
    embedded = (page.metadata or {}).get("platform_data") or {}
    team = embedded.get("team") or {}
    if not team and http_post is not None:
        payload = {
            "query": (
                'query { team(handle: "%s") { name offers_bounties state '
                "bounty_table { bounty_table_rows { nodes { low medium high critical } } } } }"
            ) % handle
        }
        result = _call_json(http_post, "https://hackerone.com/graphql", payload)
        if result and isinstance(result.get("data"), dict):
            team = result["data"].get("team") or {}

    signals = [f"hackerone program handle '{handle}'"]
    if not team:
        signals.append("no public team data")
        return PageTypeResult("unknown", 0.35, signals, "hackerone", handle)

    data: dict = {"team": team}
    offers = team.get("offers_bounties")
    if offers is True:
        data["offers_bounties"] = True
        signals.append("graphql offers_bounties=true")
    elif offers is False:
        data["offers_bounties"] = False
        signals.append("graphql offers_bounties=false")
    else:
        signals.append("graphql offers_bounties missing")
        data["payment_ambiguous"] = True
    state = team.get("state")
    if state:
        signals.append(f"program state {state}")
    return PageTypeResult("official_program", 0.98, signals, "hackerone", handle, data)


def _bugcrowd(page: PageContent, http_post: Optional[Callable]) -> Optional[PageTypeResult]:
    host = _host(page)
    if not _host_is(host, "bugcrowd.com"):
        return None
    parts = _segments(page.final_url or page.url)
    first = parts[0].lower() if parts else ""
    if first == "engagements" and len(parts) >= 2:
        slug = parts[1]
    elif len(parts) == 1 and first not in _BUGCROWD_DIRECTORY:
        slug = first
    elif first in _BUGCROWD_DIRECTORY:
        kind = "directory" if first in ("", "engagements", "programs", "customers") else "marketing"
        return PageTypeResult(kind, 0.9, [f"bugcrowd directory path '/{first}'"], "bugcrowd")
    else:
        return PageTypeResult("unknown", 0.3, ["unrecognised bugcrowd path"], "bugcrowd")

    data = _embedded_json(page)
    title = _title(page)
    description = _description(page)
    signals = [f"bugcrowd program '{slug}'"]
    reward = data.get("rewardAllocation")
    program_data: dict = {"embedded": data}
    if reward == "pay_for_success":
        program_data["offers_bounties"] = True
        signals.append("embedded rewardAllocation=pay_for_success")
    elif reward:
        program_data["payment_ambiguous"] = True
        signals.append(f"embedded rewardAllocation={reward} is unknown")
    elif re.search(r"vdp|vulnerability disclosure", title + " " + description, re.IGNORECASE):
        program_data["offers_bounties"] = False
        signals.append("title/description identifies a VDP")
    elif re.search(r"bug bounty", title, re.IGNORECASE):
        program_data["payment_ambiguous"] = True
        signals.append("title says bug bounty but no payment data")
    else:
        program_data["payment_ambiguous"] = True
        signals.append("no payment data in embedded JSON or metadata")
    if title:
        signals.append(f"title: {title[:120]}")
    return PageTypeResult("official_program", 0.9, signals, "bugcrowd", slug, program_data)


def _intigriti(page: PageContent, http_post: Optional[Callable]) -> Optional[PageTypeResult]:
    host = _host(page)
    if not _host_is(host, "intigriti.com"):
        return None
    parts = _segments(page.final_url or page.url)
    first = parts[0].lower() if parts else ""
    if first == "programs" and len(parts) >= 3:
        return PageTypeResult(
            "official_program", 0.9,
            [f"intigriti program '{parts[1]}/{parts[2]}'"],
            "intigriti", f"{parts[1]}/{parts[2]}", {},
        )
    if first in _INTIGRITI_DIRECTORY:
        return PageTypeResult("directory", 0.85, [f"intigriti directory path '/{first}'"], "intigriti")
    return PageTypeResult("unknown", 0.3, ["unrecognised intigriti path"], "intigriti")


def _google(page: PageContent, http_post: Optional[Callable]) -> Optional[PageTypeResult]:
    host = _host(page)
    if not _host_is(host, "bughunters.google.com"):
        return None
    parts = [s.lower() for s in _segments(page.final_url or page.url)]
    title = _title(page)
    is_rules = len(parts) >= 2 and parts[0] == "about" and parts[1] == "rules"
    is_vrp = bool(re.search(r"vulnerability reward program|vrp rules", title, re.IGNORECASE))
    if is_rules or is_vrp:
        return PageTypeResult(
            "official_program", 0.95,
            ["google VRP rules page" + (" (title)" if is_vrp else " (path)")],
            "google", "/".join(parts[-1:]),
            {"google_vrp_exception": True},
        )
    return PageTypeResult("marketing", 0.6, ["google bug hunters non-program page"], "google")


def detect_platform(page: PageContent) -> Optional[str]:
    host = _host(page)
    if _host_is(host, "hackerone.com"):
        return "hackerone"
    if _host_is(host, "bugcrowd.com"):
        return "bugcrowd"
    if _host_is(host, "intigriti.com"):
        return "intigriti"
    if _host_is(host, "bughunters.google.com"):
        return "google"
    return None


def resolve_platform(page: PageContent,
                     http_post: Optional[Callable] = None) -> Optional[PageTypeResult]:
    platform = detect_platform(page)
    if platform == "hackerone":
        return _hackerone(page, http_post)
    if platform == "bugcrowd":
        return _bugcrowd(page, http_post)
    if platform == "intigriti":
        return _intigriti(page, http_post)
    if platform == "google":
        return _google(page, http_post)
    return None
