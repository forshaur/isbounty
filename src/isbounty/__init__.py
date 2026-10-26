"""isBounty: Bug bounty and vulnerability disclosure policy scanner and classifier."""
from __future__ import annotations

__version__ = "0.3.0"
__author__ = "Shaurya"
__license__ = "MIT"

from .pipeline import Pipeline
from .core.models import (
    ScanResult, PageContent, PageTypeResult, PaymentEvidence,
    RewardCandidate, FirstPartyScore, DecisionResult,
)

__all__ = [
    "__version__",
    "Pipeline",
    "ScanResult",
    "PageContent",
    "PageTypeResult",
    "PaymentEvidence",
    "RewardCandidate",
    "FirstPartyScore",
    "DecisionResult",
]
