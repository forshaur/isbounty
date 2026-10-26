"""Orchestrates the full scanning flow end to end."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

import requests
import yaml

from .core.fetcher import fetch_page
from .core.first_party import score as first_party_score
from .core.decision_engine import decide
from .core.models import (
    CONTENT_OK,
    STATUS_CLASSIFIED,
    STATUS_FETCH_ERROR,
    STATUS_INSUFFICIENT,
    STATUS_NEEDS_REVIEW,
    PageContent,
    ScanResult,
)
from .core.page_type import classify_page
from .core.reward_classifier import RewardClassifier
from .core.payment_evidence import (
    add_platform_evidence,
    extract_payment_evidence,
)
from .utils.logging import get_logger

log = get_logger(__name__)

CONFIG_DIR = Path(__file__).parent / "config"

_SCOPE_HEADING_KEYWORDS = ("in scope", "out of scope", "scope", "eligib", "rules")
_REPORTING_CHANNEL_RE = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.-]+|submit (?:a |your )?report|report (?:a |the )?vulnerabilit|"
    r"bug bounty portal|security\.txt",
    re.IGNORECASE,
)

_LABEL_FOR_KIND = {
    "cash_positive": "MONETARY_POSITIVE",
    "global_no_pay": "GLOBAL_NO_PAY",
    "scoped_no_pay": "SCOPED_NEGATION",
    "recognition_only": "RECOGNITION_ONLY",
    "discretionary": "DISCRETIONARY",
    "third_party": "THIRD_PARTY",
    "historical": "HISTORICAL",
    "unclear": "UNCLASSIFIED",
}


def _load_yaml(name: str, config_dir: Path = CONFIG_DIR) -> dict:
    with open(config_dir / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _denylist_from_config(data: dict) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    keys = {
        "news_and_blog_domains": "news",
        "wiki_domains": "wiki",
        "directory_domains": "directory",
        "aggregator_domains": "aggregator",
        "marketing_domains": "marketing",
    }
    for key, category in keys.items():
        entries = data.get(key) or []
        if entries:
            mapping.setdefault(category, []).extend(entries)
    return mapping


class Pipeline:
    def __init__(self, config_dir: Path = CONFIG_DIR):
        self.config_dir = config_dir
        self.reward_patterns = _load_yaml("reward_patterns.yaml", config_dir)
        deny_data = _load_yaml("domains_denylist.yaml", config_dir)
        self.denylist_map = _denylist_from_config(deny_data)
        self.denylist = {
            entry for entries in self.denylist_map.values() for entry in entries
        }
        self.settings = _load_yaml("settings.yaml", config_dir)
        self.classifier = RewardClassifier(self.reward_patterns)

    def _scope_found(self, text: str, headings: list[str]) -> bool:
        lower = text.lower()
        if any(kw in lower for kw in _SCOPE_HEADING_KEYWORDS):
            return True
        return any(
            any(kw in h.lower() for kw in ("scope", "eligib")) for h in headings
        )

    def _reporting_channel_found(self, text: str) -> bool:
        return bool(_REPORTING_CHANNEL_RE.search(text))

    def _confidence(self, decision, page_type) -> float:
        if decision.status == STATUS_FETCH_ERROR:
            return 0.0
        if decision.status in (STATUS_INSUFFICIENT, STATUS_NEEDS_REVIEW):
            return 0.3
        if decision.label == "NOT_PROGRAM":
            return round(page_type.confidence, 2)
        if decision.label == "PAID_BB":
            return 0.92 if page_type.platform else 0.82
        return 0.78

    def _reward_candidates(self, page: PageContent, evidence: list) -> list[dict]:
        index = {sentence: i for i, sentence in enumerate(page.sentences)}
        candidates = []
        for item in evidence:
            candidates.append({
                "sentence": item.sentence,
                "context_before": "",
                "context_after": "",
                "full_window": item.clause or item.sentence,
                "sentence_index": index.get(item.sentence, -1),
                "label": _LABEL_FOR_KIND.get(item.kind, "UNCLASSIFIED"),
                "kind": item.kind,
                "reason": item.reason,
            })
        return candidates

    def run(self, url: str) -> ScanResult:
        fetch_cfg = self.settings["fetch"]
        page = fetch_page(
            url,
            timeout_seconds=fetch_cfg["timeout_seconds"],
            user_agent=fetch_cfg["user_agent"],
            use_browser_rendering=fetch_cfg.get("use_browser_rendering", False),
        )
        return self.run_from_page(page, allow_network=True)

    def run_from_page(self, page: PageContent,
                      allow_network: bool = False,
                      http_post: Optional[Callable] = None) -> ScanResult:
        """Run classification after fetching.

        Split out so tests can feed a PageContent built from a fixture without
        network access. Platform network resolvers are off unless requested.
        """
        if page is None:
            raise ValueError("page must be a PageContent instance")
        if page.content_status is None:
            page.content_status = CONTENT_OK

        post = http_post
        if post is None and allow_network:
            post = requests.post

        page_type = classify_page(
            page,
            denylist=self.denylist_map,
            http_post=post,
        )
        evidence = extract_payment_evidence(
            page, self.reward_patterns.get("triggers", [])
        )
        add_platform_evidence(page_type, evidence)
        decision = decide(page_type, page.content_status, evidence)

        reporting_channel_found = self._reporting_channel_found(page.raw_text)
        scope_found = self._scope_found(page.raw_text, page.headings)
        platform_page = bool(page_type.platform and page_type.page_type == "official_program")
        fp = first_party_score(
            page, self.settings["first_party"], applicable=not platform_page
        )

        fetch_status = page.fetch_error
        if not fetch_status and page.status_code is not None:
            fetch_status = str(page.status_code)

        return ScanResult(
            url=page.url,
            requested_url=page.requested_url or page.url,
            final_url=page.final_url or page.url,
            label=decision.label,
            confidence=self._confidence(decision, page_type),
            decision_path=decision.decision_path,
            reward_candidates=self._reward_candidates(page, evidence),
            first_party=fp.to_dict(),
            reporting_channel_found=reporting_channel_found,
            scope_found=scope_found,
            reasons=decision.reasons,
            status=decision.status,
            page_type=page_type.to_dict(),
            payment_status=decision.payment_status,
            fetch_status=fetch_status,
            evidence=[item.to_dict() for item in evidence],
        )
