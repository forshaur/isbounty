"""Sentence splitting and context-window helpers.

Stdlib regex only. This isn't linguistically perfect (abbreviations like
"e.g." can cause an over-split), but bug-bounty/VDP policy prose is mostly
short declarative sentences, and every downstream stage tolerates a few
extra splits -- the reward trigger and its window still land correctly.
"""
from __future__ import annotations

import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\u201c\"'\u2018])")


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\n+", ". ", text)
    text = re.sub(r"\s{2,}", " ", text)
    parts = _SENTENCE_BOUNDARY.split(text)
    return [p.strip() for p in parts if p.strip()]


def build_window(sentences: list[str], index: int, before: int = 1, after: int = 1) -> tuple[str, str, str]:
    """Return (context_before, context_after, full_window) for sentences[index]."""
    ctx_before = " ".join(sentences[max(0, index - before):index])
    ctx_after = " ".join(sentences[index + 1:index + 1 + after])
    sentence = sentences[index]
    full = " ".join(x for x in (ctx_before, sentence, ctx_after) if x)
    return ctx_before, ctx_after, full
