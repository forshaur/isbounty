"""Strict ordered decision table. First matching rule wins.
The rule name is always recorded so the outcome is explainable.
"""
from __future__ import annotations

from .models import RewardCandidate, FirstPartyScore, DecisionResult


def decide(
    candidates: list[RewardCandidate],
    fp: FirstPartyScore,
    reporting_channel_found: bool,
    scope_found: bool,
    first_party_high_threshold: int,
) -> DecisionResult:
    labels = {c.label for c in candidates}
    reasons: list[str] = []

    monetary = "MONETARY_POSITIVE" in labels
    global_no_pay = "GLOBAL_NO_PAY" in labels
    recognition_or_discretionary = bool(labels & {"RECOGNITION_ONLY", "DISCRETIONARY"})
    high_fp = fp.score >= first_party_high_threshold
    medium_fp = fp.score >= (first_party_high_threshold - 6)
    low_fp = fp.score >= (first_party_high_threshold - 12)

    # ------------------------------------------------------------------
    # Tier 1 – Strongest signals (highest confidence)
    # ------------------------------------------------------------------
    if monetary and high_fp and reporting_channel_found and scope_found:
        reasons.append(
            f"monetary + high first-party ({fp.score}) + reporting channel + scope"
        )
        return DecisionResult("PAID_BB", "rule_1_full_signals", reasons)

    # ------------------------------------------------------------------
    # Tier 2 – Strong monetary + most supporting signals
    # ------------------------------------------------------------------
    if monetary and high_fp and reporting_channel_found:
        reasons.append(
            f"monetary + high first-party ({fp.score}) + reporting channel "
            "(scope not explicitly detected)"
        )
        return DecisionResult("PAID_BB", "rule_2_monetary_high_fp_channel", reasons)

    if monetary and high_fp and scope_found:
        reasons.append(
            f"monetary + high first-party ({fp.score}) + scope "
            "(reporting channel not detected)"
        )
        return DecisionResult("PAID_BB", "rule_3_monetary_high_fp_scope", reasons)

    if monetary and medium_fp and reporting_channel_found and scope_found:
        reasons.append(
            f"monetary + medium first-party ({fp.score}) + channel + scope"
        )
        return DecisionResult("PAID_BB", "rule_4_monetary_medium_fp_full", reasons)

    # ------------------------------------------------------------------
    # Tier 3 – Still confident enough for real programs
    # ------------------------------------------------------------------
    if monetary and medium_fp and (reporting_channel_found or scope_found):
        reasons.append(
            f"monetary + medium first-party ({fp.score}) + "
            f"{'reporting channel' if reporting_channel_found else 'scope'}"
        )
        return DecisionResult("PAID_BB", "rule_5_monetary_medium_fp_partial", reasons)

    if monetary and high_fp:
        reasons.append(
            f"strong monetary signals + high first-party score ({fp.score}) "
            "even without clear channel/scope detection"
        )
        return DecisionResult("PAID_BB", "rule_6_monetary_high_fp_only", reasons)

    # ------------------------------------------------------------------
    # Tier 4 – Explicit VDP / no-pay paths
    # ------------------------------------------------------------------
    if global_no_pay and not monetary:
        reasons.append("explicit global no-pay statement and zero monetary positives")
        return DecisionResult("VDP", "rule_7_global_no_pay", reasons)

    if recognition_or_discretionary and not monetary and high_fp and reporting_channel_found:
        reasons.append(
            f"only recognition/discretionary language + high first-party ({fp.score}) "
            "+ reporting channel"
        )
        return DecisionResult("VDP", "rule_8_recognition_only", reasons)

    if high_fp and reporting_channel_found and scope_found and not candidates:
        reasons.append(
            "first-party policy with scope + channel but no reward language at all"
        )
        return DecisionResult("VDP", "rule_9_program_without_rewards", reasons)

    # ------------------------------------------------------------------
    # Tier 5 – Last-resort safety net for very strong monetary language
    # ------------------------------------------------------------------
    if monetary and low_fp and reporting_channel_found and scope_found:
        reasons.append(
            f"clear monetary language + channel + scope even with lower "
            f"first-party score ({fp.score})"
        )
        return DecisionResult("PAID_BB", "rule_10_monetary_low_fp_but_complete", reasons)

    # ------------------------------------------------------------------
    # Fallthrough
    # ------------------------------------------------------------------
    reasons.append(
        f"no rule matched | monetary={monetary} | global_no_pay={global_no_pay} | "
        f"recognition_or_discretionary={recognition_or_discretionary} | "
        f"fp_score={fp.score} (threshold={first_party_high_threshold}) | "
        f"channel={reporting_channel_found} | scope={scope_found}"
    )
    return DecisionResult("NOT_PROGRAM", "rule_11_fallthrough", reasons)