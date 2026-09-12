"""Orchestrates the full scanning flow end to end."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .core.fetcher import fetch_page
from .core.reward_extractor import find_reward_candidates, reward_headings_present
from .core.reward_classifier import RewardClassifier
from .core.first_party import score as first_party_score
from .core.decision_engine import decide
from .core.models import ScanResult, RewardCandidate
from .utils.logging import get_logger

log = get_logger(__name__)

CONFIG_DIR = Path(__file__).parent / "config"

_SCOPE_KEYWORDS = (
    "in scope", "out of scope", "scope", "eligible", "eligibility",
    "assets", "what is in scope", "program scope", "in-scope", "out-of-scope"
)

_REPORTING_CHANNEL_RE = re.compile(
    r"[\w.+-]+@[\w.-]+\.\w+"                                 # any email
    r"|submit (?:a |your )?report"
    r"|report (?:a |the |this )?vulnerabilit"
    r"|send (?:your |the )?report"
    r"|bug bounty portal"
    r"|security\.txt"
    r"|responsible[- ]disclosure@"
    r"|bugbounty@"
    r"|security@",
    re.IGNORECASE,
)

_INSTITUTIONAL_PRONOUN_RE = re.compile(r"\b(we|our|us)\b", re.IGNORECASE)


def _load_yaml(name: str, config_dir: Path = CONFIG_DIR) -> dict:
    with open(config_dir / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class Pipeline:
    def __init__(self, config_dir: Path = CONFIG_DIR):
        self.config_dir = config_dir
        self.reward_patterns = _load_yaml("reward_patterns.yaml", config_dir)
        self.denylist = set(_load_yaml("domains_denylist.yaml", config_dir)["news_and_blog_domains"])
        self.settings = _load_yaml("settings.yaml", config_dir)
        self.classifier = RewardClassifier(self.reward_patterns)

    def _structural_reject(self, domain: str, text: str) -> str | None:
        if domain in self.denylist:
            return f"domain '{domain}' is on the news/blog denylist"

        pronoun_hits = len(_INSTITUTIONAL_PRONOUN_RE.findall(text))
        # Softened: only reject if there is *zero* institutional language
        # and the page is also missing a reporting channel.
        has_channel = bool(_REPORTING_CHANNEL_RE.search(text))
        if pronoun_hits == 0 and not has_channel:
            return "no first-person institutional language and no reporting channel found"

        if not has_channel and pronoun_hits < 3:
            return "very weak institutional voice and no plausible reporting channel"

        return None

    def _scope_found(self, text: str, headings: list[str]) -> bool:
        lower = text.lower()
        if any(kw in lower for kw in _SCOPE_KEYWORDS):
            return True
        for h in headings:
            h_low = h.lower()
            if any(kw in h_low for kw in ("scope", "eligible", "eligibility", "assets", "in-scope", "out-of-scope")):
                return True
        return False

    def _reporting_channel_found(self, text: str) -> bool:
        return bool(_REPORTING_CHANNEL_RE.search(text))

    def _confidence(self, label: str, candidates: list, fp_score: int) -> float:
        cfg = self.settings["confidence"]
        if label == "NOT_PROGRAM":
            return cfg["not_program_default"]

        monetary_count = sum(1 for c in candidates if c.label == "MONETARY_POSITIVE")
        conflicting = len({c.label for c in candidates} & {"GLOBAL_NO_PAY", "MONETARY_POSITIVE"}) > 1

        base = cfg["base"]
        base += min(monetary_count * cfg["monetary_hit_bonus"], cfg["max_monetary_bonus"])
        base += min(fp_score / cfg["first_party_score_divisor"], cfg["max_first_party_bonus"])
        if conflicting:
            base -= cfg["conflict_penalty"]
        return round(max(cfg["floor"], min(base, cfg["ceiling"])), 2)

    def run(self, url: str) -> ScanResult:
        fetch_cfg = self.settings["fetch"]
        page = fetch_page(
            url,
            timeout_seconds=fetch_cfg["timeout_seconds"],
            user_agent=fetch_cfg["user_agent"],
            use_browser_rendering=fetch_cfg["use_browser_rendering"],
        )
        return self.run_from_page(page)

    def run_from_page(self, page) -> ScanResult:
        url = page.url
        reject_reason = self._structural_reject(page.domain, page.raw_text)
        if reject_reason:
            log.info(f"structural reject for {url}: {reject_reason}")
            return ScanResult(
                url=url, label="NOT_PROGRAM",
                confidence=self.settings["confidence"]["structural_reject_default"],
                decision_path="structural_reject", reward_candidates=[],
                first_party={}, reporting_channel_found=False, scope_found=False,
                reasons=[reject_reason],
            )

        window_cfg = self.settings["context_window"]
        candidates = find_reward_candidates(
            page, self.reward_patterns["triggers"],
            window_before=window_cfg["sentences_before"],
            window_after=window_cfg["sentences_after"],
        )

        # Also surface headings that look like reward sections
        reward_heads = reward_headings_present(
            page.headings, self.reward_patterns.get("heading_keywords", [])
        )
        if reward_heads and not candidates:
            # Create a synthetic candidate from the heading so the classifier
            # at least sees that a reward section exists.
            synthetic = RewardCandidate(
                sentence=reward_heads[0],
                context_before="",
                context_after="",
                full_window=reward_heads[0],
                sentence_index=-1,
            )
            candidates.append(synthetic)

        self.classifier.classify_all(candidates)

        reporting_channel_found = self._reporting_channel_found(page.raw_text)
        scope_found = self._scope_found(page.raw_text, page.headings)
        fp = first_party_score(page, self.settings["first_party"])

        decision = decide(
            candidates, fp, reporting_channel_found, scope_found,
            first_party_high_threshold=self.settings["first_party"]["high_threshold"],
        )
        confidence = self._confidence(decision.label, candidates, fp.score)

        return ScanResult(
            url=url, label=decision.label, confidence=confidence,
            decision_path=decision.decision_path,
            reward_candidates=[c.to_dict() for c in candidates],
            first_party=fp.to_dict(),
            reporting_channel_found=reporting_channel_found,
            scope_found=scope_found,
            reasons=decision.reasons,
        )