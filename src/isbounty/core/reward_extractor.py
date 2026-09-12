"""Locate every sentence that talks about rewards, with a local context
window around it, ready for classification.
"""
from __future__ import annotations

import re

from .models import RewardCandidate, PageContent
from .text_utils import build_window


def _compile_trigger_regex(triggers: list[str]) -> re.Pattern:
    return re.compile(r"\b(" + "|".join(triggers) + r")\b", re.IGNORECASE)


def find_reward_candidates(page: PageContent, triggers: list[str],
                            window_before: int = 1, window_after: int = 1) -> list[RewardCandidate]:
    trigger_re = _compile_trigger_regex(triggers)
    candidates: list[RewardCandidate] = []

    for i, sentence in enumerate(page.sentences):
        if trigger_re.search(sentence):
            before, after, full = build_window(page.sentences, i, window_before, window_after)
            candidates.append(RewardCandidate(
                sentence=sentence, context_before=before, context_after=after,
                full_window=full, sentence_index=i,
            ))

    return candidates


def reward_headings_present(headings: list[str], heading_keywords: list[str]) -> list[str]:
    """Headings that reference reward/bounty/compensation/etc, in case the
    body sentence extraction missed a table or bullet list under them."""
    hits = []
    for h in headings:
        low = h.lower()
        if any(kw in low for kw in heading_keywords):
            hits.append(h)
    return hits
