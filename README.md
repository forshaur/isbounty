# isBounty

[![PyPI version](https://img.shields.io/pypi/v/isbounty.svg)](https://pypi.org/project/isbounty/)
[![Python versions](https://img.shields.io/pypi/pyversions/isbounty.svg)](https://pypi.org/project/isbounty/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**isBounty** is a high-throughput, explainable scanner and classifier for Bug Bounty and Vulnerability Disclosure Policies (VDP). It analyzes security policy documents, detects reward provisions (cash rewards, bounties, Hall of Fame, swag), verifies authentic first-party reporting channels and safe harbor terms, and outputs a deterministic classification with complete reasoning and evidence provenance.

---

## Overview

Security researchers, asset management platforms, and threat intelligence pipelines frequently process thousands of target domains without a reliable way to differentiate between:
- Active, paid bug bounty programs (`PAID_BB`)
- Vulnerability disclosure programs without monetary compensation (`VDP`)
- Non-program web pages such as blogs, news articles, directories, or marketing content (`NOT_PROGRAM`)
- Inaccessible or blocked targets (`FETCH_ERROR`, `INSUFFICIENT_CONTENT`)

isBounty resolves this by implementing a layered, rule-based classification methodology rather than brittle keyword matching or non-deterministic LLM evaluation.

---

## Classification Methodology

isBounty processes documents through a multi-stage deterministic pipeline:

```
[Target URL]
     │
     ▼
[Stage 1: Fetch & Normalization] ──> Content Extraction, security.txt resolution, HTML cleaning
     │
     ▼
[Stage 2: Page Type Analysis] ─────> Platform recognition (HackerOne, Bugcrowd, Intigriti, YesWeHack),
     │                               denylist evaluation, article/directory heuristics
     │
     ▼
[Stage 3: Evidence Extraction] ────> Clause segmentation, multi-dimensional payment classification
     │                               (polarity, scope, tense, subject)
     │
     ▼
[Stage 4: First-Party Scoring] ────> Ownership verification, institutional pronouns, safe harbor,
     │                               domain asset correlation
     │
     ▼
[Stage 5: Decision Engine] ────────> Ordered evaluation rules with deterministic precedence
     │
     ▼
[Classification Result] ───────────> Label, confidence score, decision rule, and audit trace
```

### 1. Document Acquisition and Normalization
- **HTTP Fetching**: Requests pages with standard browser headers, following redirects and tracking requested vs. canonical destination URLs.
- **Headless Browser Rendering**: Optional Playwright Chromium integration for client-rendered Single Page Applications (SPAs).
- **security.txt Ingestion**: Discovers and parses `/.well-known/security.txt` and `/security.txt` fields (`Contact`, `Policy`, `Hiring`, `Acknowledgments`).
- **Text & Structure Extraction**: Strips navigation, headers, footers, boilerplate, and scripts, producing clean text chunks, structural headings, and sentence arrays.

### 2. Page Type Categorization
Before evaluating payment language, the scanner classifies the nature of the page:
- `official_program`: Self-hosted policy page or verified crowd-security platform program.
- `aggregator` / `directory`: Third-party listings of bug bounty programs (e.g., directory lists).
- `news` / `blog`: Articles, vulnerability writeups, or journalistic reporting.
- `wiki`: Reference or encyclopedic entries.
- `closed_program`: Archived, decommissioned, or paused programs.

Pages identified as non-programs (`news`, `blog`, `wiki`, `directory`) are immediately marked `NOT_PROGRAM` to prevent false positives from quoted reward figures in news stories.

### 3. Multi-Dimensional Payment Evidence Extraction
Rather than basic keyword matches, payment phrases are parsed into structured evidence objects categorized by four dimensions:
- **Polarity**: Positive (commitment to pay) vs. Negative (statement of non-payment).
- **Scope**: Global (applies to whole program) vs. Scoped (applies only to specific findings, e.g., "no bounty for out-of-scope targets").
- **Tense**: Current (active terms) vs. Historical (past programs, e.g., "we previously ran a cash bounty").
- **Subject**: First-party commitment ("we pay") vs. Third-party ("researcher was paid by Google").

### 4. Supporting First-Party Verification
The system analyzes ownership indicators to guarantee that the text represents an authentic policy issued by the domain owner:
- Institutional pronouns (`we`, `our`, `us`) vs. third-person markers (`the company`, `the researcher`, `according to`).
- Valid security reporting channels (security email addresses, submission forms, PGP keys).
- Legal safe harbor statements ("authorized research", "good faith", "will not pursue legal action").
- Domain asset correlation between policy domain, contact emails, and hostnames.

### 5. Ordered Decision Rules
The decision engine applies strict hierarchical evaluation. First matching rule determines the outcome:

1. **Content Validity Check**: If retrieval fails or returns HTTP errors, report `fetch_error` (`STATUS_FETCH_ERROR`). If content is blocked, empty, or bot-challenged, report `insufficient_content` (`STATUS_INSUFFICIENT`).
2. **Page Type Check**: Non-program page types are labeled `NOT_PROGRAM`.
3. **Platform Authoritative Data**: Authoritative metadata from verified platforms (such as structured HackerOne or Bugcrowd responses) takes precedence.
4. **Current Global Payment Evidence**:
   - Explicit current global cash commitment + verified program context -> `PAID_BB`.
   - Conflicting statements (both global pay and global no-pay detected) -> flagged for manual verification (`STATUS_NEEDS_REVIEW`).
   - Explicit current global no-pay statement ("we do not offer monetary rewards", "recognition only") -> `VDP`.
5. **VDP Fallthrough**: Official program page with established reporting channels and scope, but zero affirmative cash statements -> `VDP`.
6. **Ambiguity Handling**: Pages where program status or reward structure cannot be verified with certainty are designated `needs_review` (`STATUS_NEEDS_REVIEW`) rather than misclassified.

---

## Output Labels and Statuses

### Classification Labels
- `PAID_BB`: Official program offering monetary bounties or cash rewards.
- `VDP`: Vulnerability Disclosure Program offering non-monetary recognition (Hall of Fame, acknowledgments, swag, or safe harbor only).
- `NOT_PROGRAM`: Content confirmed to be non-policy material (news, writeup, product documentation).
- `None`: Emitted when operational issues prevent classification.

### Operational Status Codes and Process Exit Codes

| Status | Interpretation | CLI Display | Process Exit Code |
|---|---|---|---|
| `classified` | Successfully classified with high confidence | `PAID_BB`, `VDP`, `NOT_PROGRAM` | `0` |
| `fetch_error` | Network failure, DNS error, or HTTP error | `FETCH_ERROR` | `2` |
| `insufficient_content` | Empty body, bot-wall, or paywall | `UNKNOWN (insufficient content)` | `3` |
| `needs_review` | Ambiguous signals or conflicting statements | `UNKNOWN (needs review)` | `3` |

`NOT_PROGRAM` is reserved strictly for confirmed non-policy content and is never used as an error fallback.

---

## System Requirements

- Python >= 3.9
- Operating Systems: Linux, macOS, Windows
- Network connectivity for live scanning

---

## Installation

### Standard Installation
```bash
pip install isbounty
```

### Installation with Browser Rendering (Playwright)
Required for single-page applications (SPAs) and JavaScript-rendered portals:
```bash
pip install "isbounty[playwright]"
playwright install chromium
```

### Installation from Source
```bash
git clone https://github.com/forshaur/isbounty.git
cd isbounty
pip install -e .
```

---

## Command Line Interface (CLI)

### Single Target Scan
```bash
isbounty https://example.com/security
```

### Multiple Targets
```bash
isbounty https://target1.com/security https://target2.com/bug-bounty
```

### Structured JSON Output
Provide `--json` for automated ingestion into security pipelines and data lakes:
```bash
isbounty --json https://example.com/security
```

#### JSON Output Schema
```json
{
  "url": "https://example.com/security",
  "requested_url": "https://example.com/security",
  "final_url": "https://example.com/security/policy",
  "status": "classified",
  "label": "PAID_BB",
  "confidence": 0.95,
  "decision_path": "official_program_current_cash",
  "payment_status": "paid",
  "fetch_status": "200",
  "reporting_channel_found": true,
  "scope_found": true,
  "reasons": [
    "official program with current cash payment evidence"
  ],
  "page_type": {
    "page_type": "official_program",
    "confidence": 0.95,
    "platform": null
  },
  "first_party": {
    "score": 35,
    "breakdown": {
      "institutional_pronoun_hits": 14,
      "same_domain_asset_mentions": 6,
      "own_reporting_channel": true,
      "safe_harbor_language": true,
      "third_person_markers": 0,
      "security_txt_present": true
    }
  },
  "evidence": [
    {
      "kind": "cash_positive",
      "clause": "We reward security researchers with bounties up to $10,000 for qualifying reports.",
      "polarity": "positive",
      "scope": "global",
      "time": "current",
      "subject": "first_party"
    }
  ],
  "reward_candidates": [
    {
      "sentence": "We reward security researchers with bounties up to $10,000 for qualifying reports.",
      "sentence_index": 3,
      "label": "MONETARY_POSITIVE",
      "kind": "cash_positive",
      "reason": "cash_positive regex match"
    }
  ]
}
```

---

## Python API

### Basic Usage
```python
from isbounty import Pipeline

pipeline = Pipeline()
result = pipeline.run("https://example.com/security")

if result.status == "classified":
    print(f"URL: {result.url}")
    print(f"Classification: {result.label}")
    print(f"Confidence: {result.confidence}")
    print(f"Decision Rule: {result.decision_path}")
else:
    print(f"Scan status: {result.status} (Reasons: {result.reasons})")
```

### In-Memory / Offline Document Evaluation
Analyze pre-fetched HTML or custom document models without network dependencies:

```python
from isbounty import Pipeline, PageContent
from isbounty.core.text_utils import split_sentences

document_text = """
Acme Security Vulnerability Disclosure Policy
We value the work of security researchers. Acme provides monetary rewards 
ranging from $250 to $5,000 for critical issues reported to security@acme.example.
Testing against out-of-scope assets is strictly prohibited.
"""

page = PageContent(
    url="https://acme.example/security",
    raw_text=document_text,
    sentences=split_sentences(document_text),
    headings=["Vulnerability Disclosure Policy"],
    domain="acme.example",
    security_txt=None
)

pipeline = Pipeline()
result = pipeline.run_from_page(page)

print(result.label)          # 'PAID_BB'
print(result.payment_status) # 'paid'
```

---

## Configuration and Rule Customization

All classification parameters, regex heuristics, and domain classifications are managed declaratively in `src/isbounty/config/`:

- **`settings.yaml`**: Network timeouts, HTTP user-agent identity, and scoring weights for first-party signals.
- **`reward_patterns.yaml`**: Regex patterns for triggers, monetary currencies, recognition tokens, and scoped exclusion clauses.
- **`domains_denylist.yaml`**: Maintained domain mappings for news publishers, writeup aggregators, technology wikis, and directories.

### Custom Configuration Directory
Deploy private rule adjustments without modifying package files:
```python
from pathlib import Path
from isbounty import Pipeline

pipeline = Pipeline(config_dir=Path("/etc/isbounty/config"))
```

---

## Development and Verification

Run the test suite, including synthetic tests and golden fixtures:
```bash
pip install "isbounty[dev]"
python -m pytest tests/ -v
```

---

## License

This software is released under the [MIT License](LICENSE).
