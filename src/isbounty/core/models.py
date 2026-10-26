"""Shared dataclasses for every intermediate object in the pipeline.

Kept dependency-free (stdlib only) so any stage can import this module
without pulling in requests/bs4/yaml.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
from urllib.parse import urlparse


CONTENT_OK = "ok"
CONTENT_INSUFFICIENT = "insufficient_content"
CONTENT_FETCH_ERROR = "fetch_error"

STATUS_CLASSIFIED = "classified"
STATUS_INSUFFICIENT = "insufficient_content"
STATUS_FETCH_ERROR = "fetch_error"
STATUS_NEEDS_REVIEW = "needs_review"


@dataclass
class PageContent:
    url: str
    raw_text: str
    sentences: list[str]
    headings: list[str]
    domain: str
    security_txt: Optional[str] = None
    requested_url: Optional[str] = None
    final_url: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    json_ld: list[dict] = field(default_factory=list)
    fetch_error: Optional[str] = None
    content_status: str = CONTENT_OK
    security_txt_fields: dict = field(default_factory=dict)
    host: Optional[str] = None
    raw_html: Optional[str] = None

    def __post_init__(self):
        if self.requested_url is None:
            self.requested_url = self.url
        if self.final_url is None:
            self.final_url = self.url
        if self.host is None:
            self.host = (urlparse(self.final_url).hostname or "").lower()
        if not self.domain:
            self.domain = self.host

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PageTypeResult:
    page_type: str
    confidence: float = 0.5
    signals: list[str] = field(default_factory=list)
    platform: Optional[str] = None
    program_id: Optional[str] = None
    program_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PaymentEvidence:
    kind: str
    sentence: str = ""
    clause: str = ""
    subject: str = "unknown"
    polarity: str = "positive"
    scope: str = "global"
    time: str = "current"
    payment_type: str = "unclear"
    amount: Optional[str] = None
    currency: Optional[str] = None
    reason: str = ""
    current: Optional[bool] = None

    def __post_init__(self):
        if self.current is None:
            self.current = self.time == "current"

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
    label: Optional[str]
    decision_path: str
    reasons: list[str] = field(default_factory=list)
    status: str = STATUS_CLASSIFIED
    payment_status: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    url: str
    label: Optional[str]
    confidence: float
    decision_path: str
    reward_candidates: list[dict]
    first_party: dict
    reporting_channel_found: bool
    scope_found: bool
    reasons: list[str] = field(default_factory=list)
    status: str = STATUS_CLASSIFIED
    page_type: Optional[dict] = None
    payment_status: str = "unknown"
    requested_url: Optional[str] = None
    final_url: Optional[str] = None
    fetch_status: Optional[str] = None
    evidence: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.requested_url is None:
            self.requested_url = self.url
        if self.final_url is None:
            self.final_url = self.url

    def to_dict(self) -> dict:
        return asdict(self)
