"""Score how much a page reads like the domain owner's own official policy."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import PageContent, FirstPartyScore

_PRONOUNS = re.compile(r"\b(we|our|us)\b", re.IGNORECASE)
_THIRD_PERSON = re.compile(
    r"\b(the company|they|the researcher|according to|a teenager|researcher earned)\b",
    re.IGNORECASE,
)
_SAFE_HARBOR = re.compile(
    r"safe harbou?r|authorized (?:research|testing)|good[- ]faith|"
    r"we will not (?:pursue|take) legal action|"
    r"considered authorized",
    re.IGNORECASE,
)
_REPORTING_CHANNEL = re.compile(
    r"submit (?:a |your |the )?(?:vulnerability|report|bug)"
    r"|report (?:a |the )?vulnerabilit"
    r"|docs\.google\.com/forms"
    r"|bug bounty portal"
    r"|security\.txt"
    r"|send (?:your |the )?report",
    re.IGNORECASE,
)


def _related_domain(email_domain: str, page_domain: str) -> bool:
    """Treat common related domains as 'own' (e.g. htx-inc.com for htx.com)."""
    if email_domain == page_domain:
        return True
    # Simple heuristic: same second-level name
    email_base = email_domain.split(".")[0]
    page_base = page_domain.split(".")[0]
    return email_base == page_base or email_base.startswith(page_base) or page_base.startswith(email_base)


def score(page: PageContent, settings: dict) -> FirstPartyScore:
    text = page.raw_text
    lower = text.lower()
    breakdown: dict = {}
    total = 0

    pronoun_hits = len(_PRONOUNS.findall(text))
    breakdown["institutional_pronoun_hits"] = pronoun_hits
    total += min(pronoun_hits, settings["pronoun_point_cap_hits"])

    domain_mentions = lower.count(page.domain.lower())
    breakdown["same_domain_asset_mentions"] = domain_mentions
    total += min(domain_mentions * settings["domain_mention_point_multiplier"],
                 settings["max_domain_mention_points"])

    # Reporting channel – now more generous
    has_channel = bool(_REPORTING_CHANNEL.search(text))
    own_email_match = re.search(r"[\w.+-]+@([\w.-]+\.\w+)", lower)
    if own_email_match:
        email_dom = own_email_match.group(1)
        if _related_domain(email_dom, page.domain):
            has_channel = True

    breakdown["own_reporting_channel"] = has_channel
    total += settings["reporting_channel_points"] if has_channel else 0

    has_safe_harbor = bool(_SAFE_HARBOR.search(text))
    breakdown["safe_harbor_language"] = has_safe_harbor
    total += settings["safe_harbor_points"] if has_safe_harbor else 0

    third_person_hits = len(_THIRD_PERSON.findall(text))
    breakdown["third_person_markers"] = third_person_hits
    total -= min(third_person_hits * settings["third_person_penalty_per_hit"],
                 settings["max_third_person_penalty"])

    breakdown["security_txt_present"] = page.security_txt is not None
    if page.security_txt:
        total += 5

    return FirstPartyScore(score=max(total, 0), breakdown=breakdown)