# isBounty 🎯

[![PyPI version](https://img.shields.io/pypi/v/isbounty.svg)](https://pypi.org/project/isbounty/)
[![Python versions](https://img.shields.io/pypi/pyversions/isbounty.svg)](https://pypi.org/project/isbounty/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**isBounty** is a fast, explainable scanner and classifier for Bug Bounty and Vulnerability Disclosure Policies (VDP). It analyzes security policy pages, identifies reward structures (cash rewards, Hall of Fame, swag), detects official reporting channels and safe harbor provisions, and outputs a clear, confidence-scored classification with a full audit trail.

---

## 🌟 Key Features

- **Accurate Policy Classification**: Categorizes target policy pages into `PAID_BB` (Paid Bug Bounty), `VDP` (Vulnerability Disclosure Program / Hall of Fame / Swag), or `NOT_PROGRAM`. Blocked or thin pages return an operational status (`insufficient_content`, `fetch_error`, `needs_review`) instead of a guessed label.
- **Explainable Decision Engine**: Every classification cites specific rules, reasons, sentence matches, and first-party verification scores.
- **First-Party vs Third-Party Detection**: Distinguishes between an organization's genuine disclosure policy and third-party news/blog coverage.
- **Dual Fetch Engine**: Fast HTTP requests with HTML cleaning, with optional headless Playwright browser rendering for single-page applications (SPA).
- **security.txt Support**: Automatically detects and parses `/.well-known/security.txt` and `/security.txt`.
- **CLI & Python API**: Use it directly in the terminal, in automated pipelines, or embed it as a Python module.

---

## 🚀 Installation

### From PyPI
```bash
pip install isbounty
```

### With Headless Browser Rendering (Playwright)
To enable rendering JavaScript-heavy pages:
```bash
pip install "isbounty[playwright]"
playwright install chromium
```

### From Source
```bash
git clone https://github.com/Shaurya/isBounty.git
cd isBounty
pip install -e .
```

---

## 💻 CLI Usage

### Basic Scan
Scan one or more URLs:
```bash
isbounty https://example.com/security
```

### Multiple URLs
```bash
isbounty https://target1.com/bug-bounty https://target2.com/security
```

### JSON Output
Output complete evidence trails, sentence extractions, and scoring breakdowns:
```bash
isbounty --json https://example.com/security
```

Sample JSON Output:
```json
{
  "url": "https://example.com/security",
  "label": "PAID_BB",
  "confidence": 0.95,
  "decision_path": "rule_1_monetary_first_party_channel_scope",
  "reporting_channel_found": true,
  "scope_found": true,
  "reasons": [
    "monetary reward statement found; first-party score 35 >= 25; reporting channel and scope/rules both present"
  ],
  "first_party": {
    "score": 35,
    "breakdown": {
      "institutional_pronoun_hits": 12,
      "same_domain_asset_mentions": 8,
      "own_reporting_channel": true,
      "safe_harbor_language": true,
      "third_person_markers": 0,
      "security_txt_present": true
    }
  },
  "reward_candidates": [
    {
      "label": "MONETARY_POSITIVE",
      "sentence_index": 4,
      "sentence": "We offer cash rewards of up to $5,000 for qualifying critical vulnerabilities."
    }
  ]
}
```

---

## 🐍 Python Library API

You can easily embed `isBounty` into your own Python applications:

```python
from isbounty import Pipeline

pipeline = Pipeline()

# Scan any live policy URL
result = pipeline.run("https://example.com/security")

print(f"Result Label: {result.label}")              # 'PAID_BB', 'VDP', 'NOT_PROGRAM', or None
print(f"Status:       {result.status}")             # 'classified', 'insufficient_content', 'fetch_error', 'needs_review'
print(f"Page type:    {result.page_type}")          # official_program, wiki, directory, ...
print(f"Payment:      {result.payment_status}")     # paid, unpaid, unknown, conflicting
print(f"Confidence:   {result.confidence}")         # e.g., 0.95
print(f"Rule:         {result.decision_path}")
print(f"Reasons:      {result.reasons}")
```

### Offline / Custom HTML Scanning
You can also scan pre-fetched or synthetic content directly without live network requests:

```python
from isbounty import Pipeline, PageContent
from isbounty.core.text_utils import split_sentences

body = "Acme Corp operates a bug bounty program. We pay bounties up to $2,500. Report to security@acme.com."
page = PageContent(
    url="https://acme.com/bounty",
    raw_text=body,
    sentences=split_sentences(body),
    headings=["Bug Bounty Rules"],
    domain="acme.com",
    security_txt=None
)

pipeline = Pipeline()
result = pipeline.run_from_page(page)
print(result.label)  # 'PAID_BB'
```

`run_from_page` does not make platform network calls by default. Pass
`allow_network=True` or an `http_post` callable if you need live HackerOne
GraphQL resolution.

### Statuses and exit codes

| Status | CLI output | Exit code |
|---|---|---|
| `classified` | the label (`PAID_BB`, `VDP`, `NOT_PROGRAM`) | 0 |
| `insufficient_content` | `UNKNOWN (insufficient content)` | 3 |
| `needs_review` | `UNKNOWN (needs review)` | 3 |
| `fetch_error` | `FETCH_ERROR` | 2 |

`NOT_PROGRAM` is never used as an error bucket.

---

## ⚙️ Configuration

`isBounty` includes declarative YAML configurations in `isbounty/config/`:
- **`settings.yaml`**: Request user agent, timeouts, and supporting first-party weights.
- **`reward_patterns.yaml`**: Reward triggers and legacy heuristic patterns. Clause-level payment evidence lives in `core/payment_evidence.py`.
- **`domains_denylist.yaml`**: Curated news, blog, wiki, directory and aggregator hosts. Host matching is exact or subdomain-suffix based.

You can supply your own custom config directory:
```python
from pathlib import Path
from isbounty import Pipeline

custom_pipeline = Pipeline(config_dir=Path("./my_config"))
```

---

## 🧪 Testing

Run the full test suite (including golden test fixtures from real-world policy pages):

```bash
pip install "isbounty[dev]"
python -m pytest tests
```

---

## 📦 Publishing to PyPI

1. **Build Distribution**:
   ```bash
   pip install build twine
   python -m build
   ```

2. **Check Artifacts**:
   ```bash
   twine check dist/*
   ```

3. **Upload to PyPI**:
   ```bash
   twine upload dist/*
   ```

*(Alternatively, use the automated GitHub Actions workflow under `.github/workflows/publish.yml` when releasing tags.)*

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
