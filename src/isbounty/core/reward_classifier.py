"""Classify each RewardCandidate using its full context window.

Ordered rules -- first match wins, applied per candidate:
  1. MONETARY_POSITIVE  - explicit money language in the window
  2. SCOPED_NEGATION    - negation limited to a slice of the program
  3. GLOBAL_NO_PAY       - absolute "we pay nothing" language
  4. RECOGNITION_ONLY    - Hall of Fame / credit / swag, no money
  5. DISCRETIONARY       - "may", "at our discretion", no dollar amounts
  (else UNCLASSIFIED)
"""
from __future__ import annotations

import re

from .models import RewardCandidate

Patterns = dict[str, list[str]]


def _compile_group(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


class RewardClassifier:
    def __init__(self, patterns: Patterns):
        self._monetary_positive = _compile_group(patterns["monetary_positive"])
        self._scoped_negation = _compile_group(patterns["scoped_negation"])
        self._global_no_pay = _compile_group(patterns["global_no_pay"])
        self._recognition_only = _compile_group(patterns["recognition_only"])
        self._discretionary = _compile_group(patterns["discretionary"])

    @staticmethod
    def _any(compiled: list[re.Pattern], text: str) -> bool:
        return any(p.search(text) for p in compiled)

    def classify(self, candidate: RewardCandidate) -> str:
        window = candidate.full_window

        if self._any(self._monetary_positive, window):
            candidate.label = "MONETARY_POSITIVE"
        elif self._any(self._scoped_negation, window):
            candidate.label = "SCOPED_NEGATION"
        elif self._any(self._global_no_pay, window):
            candidate.label = "GLOBAL_NO_PAY"
        elif self._any(self._recognition_only, window):
            candidate.label = "RECOGNITION_ONLY"
        elif self._any(self._discretionary, window):
            candidate.label = "DISCRETIONARY"
        else:
            candidate.label = "UNCLASSIFIED"

        return candidate.label

    def classify_all(self, candidates: list[RewardCandidate]) -> list[RewardCandidate]:
        for c in candidates:
            self.classify(c)
        return candidates
