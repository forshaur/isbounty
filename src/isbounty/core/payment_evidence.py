"""Clause-level reward and payment evidence extraction.

The old classifier used the whole context window as a bag of text, so a money
mention in an adjacent sentence could override an explicit no-pay statement.
This module splits a sentence into clauses, attributes each clause to a
subject, and records polarity, scope, time and payment type.
"""
from __future__ import annotations

import re

from .models import PageContent, PageTypeResult, PaymentEvidence

_CLAUSE_SPLIT = re.compile(
    r";|,\s*(?:but|however|although|though|yet|whereas)\b", re.IGNORECASE
)
_TERM_RE = re.compile(
    r"\b(?:reward|rewards|bounty|bounties|compensation|payment|payments|"
    r"payout|paypal|monetary|money|cash|paid|pay|swag|gift cards?|recognition|"
    r"hall of fame|credit|acknowledg\w*|appreciation|non-monetary|unpaid)\b"
    r"|[$€£]\s?\d|\b(?:USD|EUR|GBP)\b",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(
    r"\b(?:not|no|never|none|without|doesn'?t|don'?t|didn'?t|isn'?t|wasn'?t|"
    r"cannot|can'?t|unpaid|non-monetary|no longer)\b",
    re.IGNORECASE,
)
_CONDITIONAL_RE = re.compile(
    r"\b(?:may|might|could|at\s+(?:our\s+)?(?:sole\s+)?discretion|"
    r"case[- ]by[- ]case|potential)\b",
    re.IGNORECASE,
)
_OTHER_RE = re.compile(
    r"\b(?:other\s+(?:companies|organizations?|organisations?|vendors?)|"
    r"another\s+(?:company|organization|organisation|vendor)|"
    r"according to|the vendor paid|they\s+(?:pay|paid|offer|offered|earned))\b",
    re.IGNORECASE,
)
_RESEARCHER_RE = re.compile(
    r"\bresearchers?\s+(?:earned|earn|were paid|was paid|received|receive)\b",
    re.IGNORECASE,
)
_OUR_RE = re.compile(
    r"\b(?:we|our|us)\b|\bthis\s+(?:program|programme|policy|bounty|vdp)\b|"
    r"\bthe\s+(?:company|organization|organisation)\b",
    re.IGNORECASE,
)
_HISTORICAL_RE = re.compile(
    r"\b(?:used to|previously|no longer|last year|last month|in 20\d\d|"
    r"former(?:ly)?|ended|past|we paid|was paid|were paid|historically)\b",
    re.IGNORECASE,
)
_FUTURE_RE = re.compile(
    r"\b(?:next year|coming soon|starting|plan(?:s|ned)? to|in the future)\b",
    re.IGNORECASE,
)
_PAYMENT_METHOD_RE = re.compile(
    r"\b(?:paypal|bank transfer|wire transfer|check|cheque|cryptocurrenc\w*|"
    r"crypto|bitcoin|venmo|ach)\b",
    re.IGNORECASE,
)
_SEVERITY_SCOPE_RE = re.compile(
    r"\b(?:low[- ]?severity|low[- ]?impact|informational|informative|critical|"
    r"high[- ]?severity|medium[- ]?severity)\b",
    re.IGNORECASE,
)
_ELIGIBILITY_SCOPE_RE = re.compile(
    r"\b(?:out[- ]of[- ]scope|third[- ]party|ineligible|eligib\w*|assets?)\b",
    re.IGNORECASE,
)
_NON_CASH_RE = re.compile(
    r"\b(?:hall of fame|public credit|public acknowledgment|acknowledg\w*|"
    r"swag|gift cards?|points?|credits?|discounts?|token of appreciation|"
    r"recognition|listed (?:on|in)|named in)\b",
    re.IGNORECASE,
)
_CASH_RE = re.compile(
    r"[$€£]\s?\d|\b(?:USD|EUR|GBP|cash|monetary|money|bank transfer|wire transfer|"
    r"paypal|check|cheque|cryptocurrenc\w*|bitcoin|paid|payout|payment|pay|"
    r"bounty payment|reward payment|compensation)\b",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(
    r"(?P<currency>[$€£])\s?(?P<amount>\d[\d,]*(?:\.\d+)?(?:\s?[kKmM])?)"
    r"|(?P<amount2>\d[\d,]*(?:\.\d+)?(?:\s?[kKmM])?)\s?(?P<currency2>USD|EUR|GBP)",
    re.IGNORECASE,
)
_GLOBAL_NO_PAY_FORMS = re.compile(
    r"\b(?:no\s+(?:paid\s+|cash\s+|monetary\s+)?(?:bug\s+)?bounty\s+program|"
    r"not\s+a\s+paid\s+(?:bug\s+)?bounty|non-monetary|unpaid|"
    r"recognition only|no\s+bounties)\b",
    re.IGNORECASE,
)


def _split_clauses(sentence: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT.split(sentence) if c and c.strip()]


def _subject(clause: str) -> str:
    if _OTHER_RE.search(clause):
        return "other_organization"
    if _RESEARCHER_RE.search(clause):
        return "researcher"
    if _OUR_RE.search(clause):
        return "our_program"
    return "unknown"


def _time(clause: str) -> str:
    if _HISTORICAL_RE.search(clause):
        return "historical"
    if _FUTURE_RE.search(clause):
        return "future"
    return "current"


def _payment_type(clause: str) -> str:
    if _NON_CASH_RE.search(clause):
        return "non_cash"
    if _CASH_RE.search(clause):
        if re.search(r"\b(?:paypal|bank transfer|wire transfer|check|cheque|"
                     r"cryptocurrenc\w*|bitcoin|venmo|ach)\b", clause, re.I):
            return "cash_equivalent"
        return "cash"
    if re.search(r"\b(?:reward|bounty|compensation)\b", clause, re.I):
        return "unclear"
    return "unclear"


def _scope(clause: str, polarity: str) -> str:
    if polarity == "positive":
        if _SEVERITY_SCOPE_RE.search(clause):
            return "severity"
        if _ELIGIBILITY_SCOPE_RE.search(clause):
            return "eligibility"
        return "global"
    if _PAYMENT_METHOD_RE.search(clause):
        return "payment_method"
    if _SEVERITY_SCOPE_RE.search(clause):
        return "severity"
    if _ELIGIBILITY_SCOPE_RE.search(clause):
        return "eligibility"
    return "global"


def _amount(clause: str) -> tuple[str | None, str | None]:
    match = _AMOUNT_RE.search(clause)
    if not match:
        return None, None
    currency = match.group("currency") or match.group("currency2")
    amount = match.group("amount") or match.group("amount2")
    mapping = {"$": "USD", "€": "EUR", "£": "GBP"}
    return amount, mapping.get(currency, currency)


def _kind(subject: str, polarity: str, scope: str, time: str,
          payment_type: str, clause: str) -> str:
    if subject in ("other_organization", "researcher"):
        return "third_party"
    if time == "historical":
        if re.search(r"no longer offer any monetary", clause, re.IGNORECASE):
            return "global_no_pay"
        return "historical"
    if polarity == "negative":
        if _GLOBAL_NO_PAY_FORMS.search(clause):
            return "global_no_pay"
        if scope == "global" and payment_type in ("cash", "cash_equivalent"):
            return "global_no_pay"
        if payment_type == "non_cash":
            return "recognition_only"
        return "scoped_no_pay"
    if polarity == "conditional":
        return "discretionary"
    if payment_type == "non_cash":
        return "recognition_only"
    if payment_type in ("cash", "cash_equivalent"):
        return "cash_positive"
    return "unclear"


def _reason(kind: str, clause: str) -> str:
    labels = {
        "cash_positive": "current cash payment language",
        "global_no_pay": "explicit global no-pay statement",
        "scoped_no_pay": "negation limited to a scope, method or severity",
        "recognition_only": "non-cash recognition or appreciation only",
        "discretionary": "conditional or discretionary reward language",
        "third_party": "reward statement about another organization or researcher",
        "historical": "historical or ended payment language",
        "unclear": "reward language without clear cash evidence",
    }
    return f"{labels.get(kind, 'reward language')}: {clause[:160]}"


def extract_payment_evidence(page: PageContent, triggers: list[str]) -> list[PaymentEvidence]:
    trigger_re = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in triggers) + r")\b", re.IGNORECASE
    )
    evidence: list[PaymentEvidence] = []
    seen: set[tuple[str, str]] = set()
    for sentence in page.sentences:
        if not (trigger_re.search(sentence) or _TERM_RE.search(sentence)):
            continue
        for clause in _split_clauses(sentence):
            if not (trigger_re.search(clause) or _TERM_RE.search(clause)):
                continue
            key = (sentence, clause)
            if key in seen:
                continue
            seen.add(key)
            subject = _subject(clause)
            polarity = "conditional" if _CONDITIONAL_RE.search(clause) else "positive"
            if _NEGATION_RE.search(clause):
                polarity = "negative"
            time = _time(clause)
            payment_type = _payment_type(clause)
            scope = _scope(clause, polarity)
            kind = _kind(subject, polarity, scope, time, payment_type, clause)
            amount, currency = _amount(clause)
            evidence.append(PaymentEvidence(
                kind=kind,
                sentence=sentence,
                clause=clause,
                subject=subject,
                polarity=polarity,
                scope=scope,
                time=time,
                payment_type=payment_type,
                amount=amount,
                currency=currency,
                reason=_reason(kind, clause),
            ))
    return evidence


def add_platform_evidence(page_type: PageTypeResult,
                          evidence: list[PaymentEvidence]) -> list[PaymentEvidence]:
    data = page_type.program_data or {}
    if data.get("offers_bounties") is True:
        evidence.append(PaymentEvidence(
            kind="cash_positive",
            subject="our_program",
            polarity="positive",
            scope="global",
            time="current",
            payment_type="cash",
            reason=f"{page_type.platform} platform reports cash bounties",
        ))
    elif data.get("offers_bounties") is False:
        evidence.append(PaymentEvidence(
            kind="global_no_pay",
            subject="our_program",
            polarity="negative",
            scope="global",
            time="current",
            payment_type="cash",
            reason=f"{page_type.platform} platform reports no cash bounties",
        ))
    if data.get("google_vrp_exception"):
        evidence.append(PaymentEvidence(
            kind="cash_positive",
            subject="our_program",
            polarity="positive",
            scope="global",
            time="current",
            payment_type="cash",
            reason="official Google VRP rules page states potential reward amounts",
        ))
    return evidence


def payment_status(evidence: list[PaymentEvidence]) -> str:
    current = [e for e in evidence if e.current]
    global_no_pay = any(
        e.kind == "global_no_pay" and e.scope == "global" for e in current
    )
    global_cash = any(
        e.kind == "cash_positive" and e.scope == "global" and e.current
        for e in evidence
    )
    any_cash = any(e.kind == "cash_positive" and e.current for e in evidence)
    if global_no_pay and global_cash:
        return "conflicting"
    if global_no_pay:
        return "unpaid"
    if any_cash:
        return "paid"
    return "unknown"
