"""Shared dataclasses for every intermediate object in the pipeline.

Kept dependency-free (stdlib only) so any stage can import this module
without pulling in requests/bs4/yaml.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class PageContent:
    url: str
    raw_text: str
    sentences: list[str]
    headings: list[str]
    domain: str
    security_txt: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RewardCandidate:
    sentence: str
    context_before: str
    context_after: str
    full_window: str
    sentence_index: int
    label: str = "UNCLASSIFIED"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FirstPartyScore:
    score: int
    breakdown: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DecisionResult:
    label: str
    decision_path: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    url: str
    label: str
    confidence: float
    decision_path: str
    reward_candidates: list[dict]
    first_party: dict
    reporting_channel_found: bool
    scope_found: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
