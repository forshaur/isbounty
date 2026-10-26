"""Ordered decision table.

Page type comes first. Only current global payment evidence participates in
the payment rules. NOT_PROGRAM is never used as an error fallthrough.
"""
from __future__ import annotations

from .models import (
    CONTENT_FETCH_ERROR,
    CONTENT_INSUFFICIENT,
    STATUS_CLASSIFIED,
    STATUS_FETCH_ERROR,
    STATUS_INSUFFICIENT,
    STATUS_NEEDS_REVIEW,
    DecisionResult,
    PageTypeResult,
    PaymentEvidence,
)
from .page_type import NON_PROGRAM_TYPES
from .payment_evidence import payment_status


def decide(page_type: PageTypeResult,
           content_status: str,
           evidence: list[PaymentEvidence]) -> DecisionResult:
    reasons: list[str] = []
    kind = page_type.page_type

    if content_status == CONTENT_FETCH_ERROR:
        reasons.append("fetch failed or returned an unusable HTTP error")
        return DecisionResult(None, "content_fetch_error", reasons, STATUS_FETCH_ERROR, "unknown")

    data = page_type.program_data or {}
    authoritative = bool(
        kind == "official_program"
        and page_type.platform
        and (
            data.get("offers_bounties") in (True, False)
            or data.get("google_vrp_exception")
            or data.get("embedded", {}).get("rewardAllocation") == "pay_for_success"
        )
    )
    if content_status == CONTENT_INSUFFICIENT and not authoritative:
        reasons.append("fetched body has no usable program content")
        return DecisionResult(None, "content_insufficient", reasons, STATUS_INSUFFICIENT, "unknown")

    if kind in NON_PROGRAM_TYPES or kind == "closed_program":
        reasons.append(f"page type '{kind}' is not an official current program")
        return DecisionResult("NOT_PROGRAM", "page_type_non_program", reasons, STATUS_CLASSIFIED, "unknown")

    if kind == "unknown":
        reasons.append("page type could not be established")
        return DecisionResult(None, "page_type_needs_review", reasons, STATUS_NEEDS_REVIEW, "unknown")

    if kind != "official_program":
        reasons.append(f"unhandled page type '{kind}'")
        return DecisionResult(None, "fallthrough_needs_review", reasons, STATUS_NEEDS_REVIEW, "unknown")

    program_data = data
    if program_data.get("multi_program_ambiguous"):
        reasons.append("page describes multiple programs and cannot be tied to one")
        return DecisionResult(None, "multi_program_ambiguous", reasons, STATUS_NEEDS_REVIEW, "conflicting")

    status = payment_status(evidence)
    if status == "unknown" and program_data.get("payment_ambiguous"):
        reasons.append("program page is official but payment evidence is ambiguous")
        return DecisionResult(None, "official_program_payment_ambiguous", reasons, STATUS_NEEDS_REVIEW, "unknown")
    if status == "conflicting":
        reasons.append("current global no-pay and current global cash evidence conflict")
        return DecisionResult(None, "official_program_conflicting_payment", reasons, STATUS_NEEDS_REVIEW, "conflicting")
    if status == "unpaid":
        reasons.append("official program with a current global no-pay statement")
        return DecisionResult("VDP", "official_program_global_no_pay", reasons, STATUS_CLASSIFIED, "unpaid")
    if status == "paid":
        reasons.append("official program with current cash payment evidence")
        return DecisionResult("PAID_BB", "official_program_current_cash", reasons, STATUS_CLASSIFIED, "paid")

    reasons.append("official program with no current cash evidence")
    return DecisionResult("VDP", "official_program_no_cash", reasons, STATUS_CLASSIFIED, "unknown")
