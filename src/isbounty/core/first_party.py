"""Supporting first-party signals.

This score is explainability evidence only. It is not a gate: a missing
pronoun or reporting channel must never turn an official policy page into
NOT_PROGRAM. security.txt presence adds no points.
"""
from __future__ import annotations

import re

from .models import PageContent, FirstPartyScore

_PRONOUNS = re.compile(r"\b(we|our|us)\b", re.IGNORECASE)
_THIRD_PERSON = re.compile(
    r"\b(the company|they|the researcher|according to|a teenager|researcher earned)\b",
    re.IGNORECASE,
)
_SAFE_HARBOR = re.compile(
    r"safe harbou?r|authorized (?:research|testing)|good[- ]faith",
    re.IGNORECASE,
)
_REPORTING_CHANNEL = re.compile(
    r"submit (?:a |your |the )?(?:vulnerability|report|bug)"
    r"|report (?:a |the )?vulnerabilit"
    r"|docs\.google\.com/forms"
    r"|bug bounty portal"
    r"|send (?:your |the )?report"
    r"|hackerone\.com/|bugcrowd\.com/|intigriti\.com/",
    re.IGNORECASE,
)
_SECURITY_EMAIL = re.compile(
    r"\b(?:security|psirt|security[-_.]?reports?|vulnerabilit(?:y|ies))"
    r"@[\w-]+(?:\.[\w-]+)+",
    re.IGNORECASE,
)
_ARTICLE_STRUCTURE = re.compile(
    r"\b(?:wiki|article|author|published|citation|read more|related articles)\b",
    re.IGNORECASE,
)


def _security_txt_channel(page: PageContent) -> bool:
    fields = page.security_txt_fields or {}
    for contact in fields.get("contact", []):
        if _SECURITY_EMAIL.search(contact):
            return True
    return bool(fields.get("policy"))


def score(page: PageContent, settings: dict, applicable: bool = True) -> FirstPartyScore:
    if not applicable:
        return FirstPartyScore(score=0, breakdown={"not_applicable": True})

    text = page.raw_text
    lower = text.lower()
    breakdown: dict = {}
    total = 0

    pronoun_hits = len(_PRONOUNS.findall(text))
    breakdown["institutional_pronoun_hits"] = pronoun_hits
    total += min(pronoun_hits, settings.get("pronoun_point_cap_hits", 12))

    domain_mentions = lower.count(page.domain.lower()) if page.domain else 0
    breakdown["same_domain_asset_mentions"] = domain_mentions
    total += min(
        domain_mentions * settings.get("domain_mention_point_multiplier", 2),
        settings.get("max_domain_mention_points", 15),
    )

    has_channel = bool(
        _SECURITY_EMAIL.search(text)
        or _REPORTING_CHANNEL.search(text)
        or _security_txt_channel(page)
    )
    breakdown["own_reporting_channel"] = has_channel
    total += settings.get("reporting_channel_points", 25) if has_channel else 0

    has_safe_harbor = bool(_SAFE_HARBOR.search(text))
    breakdown["safe_harbor_language"] = has_safe_harbor
    total += settings.get("safe_harbor_points", 8) if has_safe_harbor else 0

    third_person_hits = len(_THIRD_PERSON.findall(text))
    breakdown["third_person_markers"] = third_person_hits
    total -= min(
        third_person_hits * settings.get("third_person_penalty_per_hit", 2),
        settings.get("max_third_person_penalty", 20),
    )

    og_type = str((page.metadata or {}).get("og_type") or "").lower()
    article_hits = len(_ARTICLE_STRUCTURE.findall(text[:8000]))
    article_penalty = settings.get("article_structure_penalty", 5)
    if og_type == "article" or article_hits >= 6:
        total -= article_penalty
    breakdown["article_structure_penalty"] = article_penalty if (
        og_type == "article" or article_hits >= 6
    ) else 0

    breakdown["security_txt_present"] = page.security_txt is not None
    breakdown["security_txt_points"] = 0

    return FirstPartyScore(score=max(total, 0), breakdown=breakdown)
