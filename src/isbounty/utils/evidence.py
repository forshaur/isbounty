"""Serialize and pretty-print a ScanResult's full evidence trail."""
from __future__ import annotations

import json

from ..core.models import (
    STATUS_FETCH_ERROR,
    STATUS_INSUFFICIENT,
    STATUS_NEEDS_REVIEW,
    ScanResult,
)


def display_label(result: ScanResult) -> str:
    if result.status == STATUS_FETCH_ERROR:
        return "FETCH_ERROR"
    if result.status == STATUS_INSUFFICIENT:
        return "UNKNOWN (insufficient content)"
    if result.status == STATUS_NEEDS_REVIEW:
        return "UNKNOWN (needs review)"
    return result.label or "UNKNOWN"


def to_json(result: ScanResult, indent: int = 2) -> str:
    return json.dumps(result.to_dict(), indent=indent)


def to_human_readable(result: ScanResult) -> str:
    page_type = (result.page_type or {})
    lines = [
        f"URL:              {result.requested_url or result.url}",
        f"Final URL:        {result.final_url or result.url}",
        f"Status:           {result.status}",
        f"Label:            {display_label(result)}",
        f"HTTP/fetch:       {result.fetch_status or 'n/a'}",
        f"Confidence:       {result.confidence}",
        f"Decision rule:    {result.decision_path}",
        f"Page type:        {page_type.get('page_type', 'n/a')}",
        f"Payment status:   {result.payment_status}",
        f"Reporting channel found: {result.reporting_channel_found}",
        f"Scope/rules found:       {result.scope_found}",
        "",
        "Reasons:",
    ]
    lines += [f"  - {r}" for r in result.reasons]

    lines.append("")
    lines.append(f"First-party score: {result.first_party.get('score')}")
    for k, v in result.first_party.get("breakdown", {}).items():
        lines.append(f"  {k}: {v}")

    lines.append("")
    lines.append(f"Payment evidence ({len(result.evidence)}):")
    for item in result.evidence:
        lines.append(
            f"  [{item['kind']}] ({item['subject']}/{item['polarity']}/"
            f"{item['scope']}/{item['time']}) {item.get('clause') or item.get('reason')!r}"
        )

    lines.append("")
    lines.append(f"Reward candidates ({len(result.reward_candidates)}):")
    for c in result.reward_candidates:
        lines.append(f"  [{c['label']}] (sentence #{c['sentence_index']}) {c['sentence']!r}")

    return "\n".join(lines)
