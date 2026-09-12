"""Strict ordered decision table. First matching rule wins; the rule name
is always recorded so the outcome is explainable.
"""
from __future__ import annotations

from .models import RewardCandidate, FirstPartyScore, DecisionResult


def decide(candidates: list[RewardCandidate], fp: FirstPartyScore,
           reporting_channel_found: bool, scope_found: bool,
           first_party_high_threshold: int) -> DecisionResult:
    labels = {c.label for c in candidates}
    reasons: list[str] = []

    monetary = "MONETARY_POSITIVE" in labels
    global_no_pay = "GLOBAL_NO_PAY" in labels
    recognition_or_discretionary = bool(labels & {"RECOGNITION_ONLY", "DISCRETIONARY"})
    high_fp = fp.score >= first_party_high_threshold

    if monetary and high_fp and reporting_channel_found and scope_found:
        reasons.append(
            f"monetary reward statement found; first-party score {fp.score} "
            f">= {first_party_high_threshold}; reporting channel and scope/rules both present"
        )
        return DecisionResult("PAID_BB", "rule_1_monetary_first_party_channel_scope", reasons)

    if monetary and high_fp and reporting_channel_found:
        reasons.append(
            "monetary reward statement found with high first-party score and a reporting "
            "channel; no explicit scope/rules section detected, but the other three signals "
            "are strong enough on their own"
        )
        return DecisionResult("PAID_BB", "rule_1b_monetary_first_party_channel", reasons)

    if global_no_pay and not monetary:
        reasons.append("explicit global no-pay statement present, and no monetary "
                        "positive anywhere on the page")
        return DecisionResult("VDP", "rule_2_global_no_pay", reasons)

    if recognition_or_discretionary and not monetary and high_fp and reporting_channel_found:
        reasons.append(
            f"only recognition/discretionary reward language, no monetary commitment; "
            f"first-party score {fp.score} >= {first_party_high_threshold}; "
            f"reporting channel present"
        )
        return DecisionResult("VDP", "rule_3_recognition_or_discretionary", reasons)

    if high_fp and reporting_channel_found and scope_found and not candidates:
        reasons.append("first-party policy with scope/rules and a reporting channel, "
                        "but no reward-related language anywhere on the page")
        return DecisionResult("VDP", "rule_4_no_reward_language_but_program", reasons)

    reasons.append(
        f"no rule matched: monetary={monetary}, global_no_pay={global_no_pay}, "
        f"recognition_or_discretionary={recognition_or_discretionary}, "
        f"first_party_score={fp.score} (threshold={first_party_high_threshold}), "
        f"reporting_channel_found={reporting_channel_found}, scope_found={scope_found}"
    )
    return DecisionResult("NOT_PROGRAM", "rule_5_fallthrough", reasons)
