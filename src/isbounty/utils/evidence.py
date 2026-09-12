"""Serialize and pretty-print a ScanResult's full evidence trail."""
from __future__ import annotations

import json

from ..core.models import ScanResult


def to_json(result: ScanResult, indent: int = 2) -> str:
    return json.dumps(result.to_dict(), indent=indent)


def to_human_readable(result: ScanResult) -> str:
    lines = [
        f"URL:              {result.url}",
        f"Label:            {result.label}",
        f"Confidence:       {result.confidence}",
        f"Decision rule:    {result.decision_path}",
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
    lines.append(f"Reward candidates ({len(result.reward_candidates)}):")
    for c in result.reward_candidates:
        lines.append(f"  [{c['label']}] (sentence #{c['sentence_index']}) {c['sentence']!r}")

    return "\n".join(lines)
