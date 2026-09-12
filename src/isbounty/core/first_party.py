"""Score how much a page reads like the domain owner's own official policy,
as opposed to third-party coverage of someone else's program.
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
    r"submit (?:a |your )?report|report (?:a |the )?vulnerabilit|"
    r"bug bounty portal|security\.txt|send (?:your |the )?report",
    re.IGNORECASE,
)


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

    own_email = re.search(r"[\w.+-]+@" + re.escape(page.domain.lower()), lower)
    has_channel = bool(own_email) or bool(_REPORTING_CHANNEL.search(text))
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