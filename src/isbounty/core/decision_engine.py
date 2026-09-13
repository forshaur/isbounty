"""Strict ordered decision table. First matching rule wins."""
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
    medium_fp = fp.score >= (first_party_high_threshold - 5)   # small buffer

    # Strongest path
    if monetary and high_fp and reporting_channel_found and scope_found:
        reasons.append(
            f"monetary reward statement found; first-party score {fp.score} "
            f">= {first_party_high_threshold}; reporting channel and scope both present"
        )
        return DecisionResult("PAID_BB", "rule_1_monetary_first_party_channel_scope", reasons)

    # Resilient path – allow slightly lower first-party when other signals are strong
    if monetary and medium_fp and reporting_channel_found and scope_found:
        reasons.append(
            f"monetary + scope + reporting channel present; first-party score "
            f"{fp.score} is close to threshold ({first_party_high_threshold})"
        )
        return DecisionResult("PAID_BB", "rule_1c_monetary_medium_fp_channel_scope", reasons)

    if monetary and high_fp and reporting_channel_found:
        reasons.append(
            "monetary reward + high first-party + reporting channel "
            "(scope section not explicitly detected)"
        )
        return DecisionResult("PAID_BB", "rule_1b_monetary_first_party_channel", reasons)

    if global_no_pay and not monetary:
        reasons.append("explicit global no-pay statement and no monetary positive")
        return DecisionResult("VDP", "rule_2_global_no_pay", reasons)

    if recognition_or_discretionary and not monetary and high_fp and reporting_channel_found:
        reasons.append(
            f"only recognition/discretionary language; first-party {fp.score}; "
            f"reporting channel present"
        )
        return DecisionResult("VDP", "rule_3_recognition_or_discretionary", reasons)

    if high_fp and reporting_channel_found and scope_found and not candidates:
        reasons.append("first-party policy with scope + channel but no reward language")
        return DecisionResult("VDP", "rule_4_no_reward_language_but_program", reasons)

    reasons.append(
        f"no rule matched: monetary={monetary}, global_no_pay={global_no_pay}, "
        f"recognition_or_discretionary={recognition_or_discretionary}, "
        f"first_party_score={fp.score} (threshold={first_party_high_threshold}), "
        f"reporting_channel_found={reporting_channel_found}, scope_found={scope_found}"
    )
    return DecisionResult("NOT_PROGRAM", "rule_5_fallthrough", reasons)