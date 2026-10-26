# isBounty Classifier Improvement Specification

Status: implementation specification for a developer.
Scope: reduce false positives and false negatives in the rule-based URL classifier.
Constraint: keep the classifier rule-based and explainable. Do not add a machine-learning model.

Verified against the repository at `/home/kali/isbounty` and live examples on 2026-10-23.

## 1. Product definitions

The classifier analyses one URL and returns the status of the program described by that page.

- `PAID_BB`: the page is an official program page, and the program currently offers cash or direct cash-equivalent compensation for vulnerability reports.
- `VDP`: the page is an official program page, and the program accepts vulnerability reports but does not currently offer cash compensation. Recognition, credit, swag, gift cards, and non-cash appreciation are VDP.
- `NOT_PROGRAM`: the page is not an official program page. Examples: news, blogs, wikis, directories, aggregators, marketing pages, generic security contact pages, and pages that only discuss someone else's program.

Definitions that must remain explicit:

- An official program page is either:
  - a company or government policy page that invites vulnerability reports and describes scope, rules, or a reporting process; or
  - a specific program page hosted on a bug bounty platform.
- A platform-hosted specific program page is official even when it is not on the company's own domain.
- A platform directory, homepage, or blog is not a program page.
- A third-party article about a paid program is `NOT_PROGRAM`, even if it contains dollar amounts.
- `PAID_BB` requires cash or a direct cash transfer. Bank transfer, wire transfer, PayPal, check, and cryptocurrency count. Gift cards, swag, points, credits, discounts, and public recognition do not count unless the page explicitly defines them as a cash payment. This is a deliberate conservative rule: do not label a program paid because it mentions "reward", "bounty", or "gift card" alone.
- "Potential" or "up to" reward language is paid when the official program page states a monetary reward structure. A bare "may offer a reward" with no cash amount, payment mechanism, or platform field is VDP, not `PAID_BB`.
- Historical payments do not make a program currently paid. "We used to pay", "we no longer pay", "researchers earned last year", and "previously offered" are not current payment evidence.

Do not add `UNKNOWN` to the three classification labels. Use an operational `status` field instead. A page with no usable content is an abstention, not a `NOT_PROGRAM` result.

## 2. Verified current failures

These are observed results from the current implementation, not hypothetical cases.

### 2.1 Fetch failures

- `https://www.mozilla.org/en-US/security/bug-bounty/` returned `HTTPError: 406 Client Error: Not Acceptable` with the configured bot user agent during verification. A browser-like user agent returned HTTP 200 and the current classifier then finds `PAID_BB`. Network behaviour varies, so the fix is a browser-like request plus honest fetch status, not a hard-coded exception.
- `https://hackerone.com/security` returns HTTP 200 but the cleaned text contains only the JavaScript-disabled notice. The current classifier returns `NOT_PROGRAM` with `structural_reject`.
- `https://bughunters.google.com/about/rules/google-friends/google-and-alphabet-vulnerability-reward-program-vrp-rules` returns HTTP 200 but an empty body. It has useful title and meta description. The current classifier returns `NOT_PROGRAM` with `structural_reject`.
- `https://bugcrowd.com/tesla` redirects to `https://bugcrowd.com/engagements/tesla`. The visible body is only the login header, but the raw HTML contains program JSON. The current classifier returns `NOT_PROGRAM` with `structural_reject`.
- `https://www.intigriti.com/programs/intigriti/intigriti-bug-bounty` redirects to `https://app.intigriti.com/programs/intigriti/intigriti-bug-bounty` and returns a forbidden page. The current classifier returns `NOT_PROGRAM` with `structural_reject`. This must become an insufficient-content result if no public data source is available.

### 2.2 Structural reject false negatives

The current structural reject requires first-person `we`, `our`, or `us`, and a narrow reporting-channel pattern. Official pages that use third-person policy language or different report wording are rejected.

- `https://www.dhs.gov/vulnerability-disclosure-policy` -> `NOT_PROGRAM`; expected `VDP`.
- `https://www.gov.uk/help/report-vulnerability` -> `NOT_PROGRAM`; expected `VDP`.
- `https://mojdigital.blog.gov.uk/vulnerability-disclosure-policy` -> `NOT_PROGRAM`; expected `VDP`.
- `https://www.lodlaw.com/legal-disclosures/vulnerability-disclosure-policy` -> `NOT_PROGRAM`; expected `VDP` if rendered content is available, otherwise insufficient content.
- `https://bounty.github.com/` -> `NOT_PROGRAM`; expected `PAID_BB`.
- `https://kb.isc.org/docs/aa-00861` -> `NOT_PROGRAM`; expected `VDP` or `needs_review`. The page says "No Bounties" but also contains a footnote about a European Commission-funded one-year BIND bug bounty. `NOT_PROGRAM` is wrong either way.

The official DHS page contains no first-person institutional pronouns, yet it is clearly a disclosure program. The MOJ page contains the policy but the pipeline reports no plausible reporting channel. The pipeline's reporting pattern does not match `submit a vulnerability report`; it matches `submit reports` only because `submit report` is a prefix. The `first_party.py` and `pipeline.py` channel regexes also differ, so a page can pass one check and fail the other.

### 2.3 False positives caused by ignoring negation

The current reward classifier checks `MONETARY_POSITIVE` before `GLOBAL_NO_PAY`. Any money or reward term in the context window therefore overrides an explicit no-pay statement.

Observed `PAID_BB` results that should be `VDP`:

- `https://cyble.com/security-disclosure-policy`
- `https://www.crofting.scotland.gov.uk/vulnerability-disclosure-policy`
- `https://www.thegoodpenguin.co.uk/Vulnerability-Disclosure-Policy`
- `https://readytech.io/vulnerability-disclosure`
- `https://grand-challenge.org/vulnerability-disclosure`
- `https://www.bbc.co.uk/backstage/security-disclosure-policy/`
- `https://www.fcdoservices.gov.uk/vulnerability-reporting`

Representative evidence:

- Cyble: "We do not offer any monetary rewards for vulnerability disclosures, however, reporters of qualifying vulnerabilities may be offered a unique Cyble reward."
- Crofting, Good Penguin, ReadyTech: "However, we do not offer monetary rewards for vulnerability disclosures."
- Grand Challenge: "We do not operate a bug bounty program and do not provide monetary compensation (reward) for vulnerability reports."
- BBC: "it is not currently possible for us to offer a paid bug bounty programme."
- FCDO: "it is not currently possible for us to offer a paid bug bounty programme."

These pages are official program pages and still accept reports, so the correct result is `VDP`, not `NOT_PROGRAM`.

Synthetic cases below include a reporting channel and scope, so they test the reward classifier rather than the structural gate:

- `We do not offer monetary rewards.` -> current `PAID_BB`; expected `VDP`.
- `We do not pay via PayPal.` -> current `PAID_BB`; expected not paid, unless another positive cash clause exists.
- `Other companies pay up to $50,000.` -> current `PAID_BB`; expected not paid for this program.
- `We no longer offer a paid bug bounty.` -> current `NOT_PROGRAM`; expected `VDP` if reports are still accepted.

### 2.4 Third-party false positives

The current first-party score is too easy to satisfy. Pronoun counts, domain mentions, own-domain email, the pipeline's any-email channel check, and security.txt presence can make a third-party page look official.

Observed `PAID_BB` results that should be `NOT_PROGRAM`:

- `https://en.wikipedia.org/wiki/Bug_bounty_program` -> first-party score 24, `security_txt_present: true`.
- `https://www.hackerone.com/bug-bounty-programs` -> first-party score 40, 667 pronoun hits, 386 domain mentions.
- `https://www.hackerone.com/blog/bug-bounty-vs-vdp-which-program-right-you` -> first-party score 29.

The Wikipedia page has a valid Wikimedia security.txt with a `Contact` and `Policy` field. Security.txt presence proves a security contact, not a bug bounty or VDP. The HackerOne directory page lists many programs and says "Offers bounties. $50 minimum bounty." It is a directory, not one program.

### 2.5 Design constraint: article metadata

The current code does not parse article metadata. The Finance NI policy page has `og:type=article` and `article:published_time`, but it is an official vulnerability disclosure page:

- `https://www.finance-ni.gov.uk/articles/vulnerability-disclosure` -> current `VDP`; expected `VDP`.

GOV.UK policy pages also use article metadata. A future implementation must not reject a page solely because `og:type` is `article`, or it will create a new false negative.

### 2.6 Verified platform evidence

The current HTML-only fetch misses data that is available elsewhere.

HackerOne's public GraphQL endpoint works for the HackerOne program:

```text
POST https://hackerone.com/graphql
```

```graphql
query {
  team(handle: "security") {
    name
    offers_bounties
    state
    bounty_table {
      bounty_table_rows {
        nodes {
          low
          medium
          high
          critical
        }
      }
    }
  }
}
```

Observed response includes:

```json
{"data":{"team":{"name":"HackerOne","offers_bounties":true,"state":"public_mode"}}}
```

Bugcrowd's Tesla page contains embedded JSON, including:

```json
{"name":"Tesla","state":"in_progress","code":"tesla","rewardAllocation":"pay_for_success"}
```

The Tesla page title is "Bug Bounty: Tesla - Bugcrowd".

The Google VRP page has:

- Title: "Google and Alphabet Vulnerability Reward Program (VRP) Rules | Google Bug Hunters"
- Meta description: "Get an overview of the rules governing the Google VRP and related programs, including what’s in scope and potential reward amounts."

The Mozilla page with a browser user agent has title "Security Bug Bounty Program — Mozilla" and body content that includes "The Mozilla Security Bug Bounty Program is designed to encourage security research in Mozilla software and to reward those who help us..."

These facts justify a platform resolver and metadata extraction, not a general relaxation of the classifier.

## 3. Root causes

1. Classification is attempted before page type is established. A third-party article and an official policy page are treated as the same kind of input.
2. A missing first-person pronoun is treated as proof that a page is not a program. Official policy pages often use third-person language (`pipeline.py:36-38`).
3. Reporting-channel checks are duplicated with different regexes. The pipeline regex does not match "submit a vulnerability report"; the first-party regex does (`pipeline.py:16-20`, `first_party.py:14-22`).
4. The reward classifier is order-dependent. Monetary positives are checked before negations, so "do not offer monetary rewards" is treated as a positive (`reward_classifier.py:39-43`).
5. Negation scope is not represented. "Do not pay for low severity" and "do not pay via PayPal" are different from "do not pay at all".
6. Subject attribution is not represented. "Other companies pay" and "researchers earned" are not statements by the program operator.
7. Time is not represented. "Used to pay" and "no longer pay" are not current payment.
8. The context window is used as a bag of text. A money mention in an adjacent sentence can override a no-pay candidate.
9. First-party scoring is a gate rather than supporting evidence. Pronouns, domain mentions, own-domain email, the pipeline's any-email channel check, and security.txt presence create false positives.
10. Fetch failures are collapsed into `NOT_PROGRAM`. A blocked or JavaScript-only page becomes a false negative.
11. `security.txt` presence adds points regardless of its content (`first_party.py:46-49`). It should only support a reporting channel when its `Policy` or `Contact` fields are relevant.
12. The monetary patterns include malformed entries that match whitespace plus a digit (`reward_patterns.yaml:37-38`), and `gift card` is treated as cash. Both create false positives.
13. The domain denylist is too small and uses a naive registrable-domain function that does not match entries such as `news.ycombinator.com`. The configured user agent in `settings.yaml:5`, passed by `pipeline.py:66`, is the bot user agent that produced the observed Mozilla 406.

## 4. Required design

Use two independent questions, in this order:

1. What kind of page is this? Is it an official program page or a third-party/non-program page?
2. If it is an official program page, does the program currently pay cash?

Do not decide payment before page type. Do not require first-person pronouns. Do not use security.txt presence as program evidence.

### 4.1 Result statuses

Add an operational status to the scan result:

- `classified`: the page was classified as `PAID_BB`, `VDP`, or `NOT_PROGRAM`.
- `insufficient_content`: the page was fetched and returned a body, but the body has no usable program content, or is a JavaScript-only/login/forbidden body with no resolvable metadata.
- `fetch_error`: the request failed, timed out, returned 5xx, or returned 403/406/429 with no usable fallback page.
- `needs_review`: the page type or payment evidence is ambiguous, whether or not the page is official.

When status is not `classified`, `label` must be `None`. Do not use `NOT_PROGRAM` as an error bucket.

CLI behaviour:

- `classified`: print the label.
- `insufficient_content`: print `UNKNOWN (insufficient content)` and exit 3.
- `fetch_error`: print `FETCH_ERROR` and exit 2.
- `needs_review`: print `UNKNOWN (needs review)` and exit 3.

The three classification labels keep their current meanings. `UNKNOWN` is an operational abstention, not a fourth classification.

## 5. Data model changes

Keep the existing public entry points and result fields where possible. Add fields; do not silently change existing meanings.

### 5.1 PageContent

Add:

- `requested_url`: the URL passed to the scanner.
- `final_url`: the URL after redirects.
- `status_code`: HTTP status.
- `content_type`: response content type.
- `metadata`: title, meta description, Open Graph fields, Twitter card fields, canonical URL.
- `json_ld`: parsed JSON-LD objects.
- `fetch_error`: error message when fetching fails.
- `content_status`: `ok`, `insufficient_content`, or `fetch_error`.
- `security_txt_fields`: parsed RFC 9116 fields, not only the raw string.

Keep the existing `url` field as an alias of `requested_url`, plus `raw_text`, `sentences`, `headings`, `domain`, and `security_txt` for compatibility. Give new fields defaults so `Pipeline.run_from_page` fixtures continue to work without a fetch.

### 5.2 PageTypeResult

Add a result object with:

- `page_type`: `official_program`, `closed_program`, `news`, `blog`, `wiki`, `directory`, `aggregator`, `marketing`, `generic_security`, `unknown`.
- `confidence`: number from 0 to 1.
- `signals`: list of human-readable reasons.
- `platform`: `hackerone`, `bugcrowd`, `intigriti`, `google`, or `None`.
- `program_id`: platform handle or slug when known.

### 5.3 PaymentEvidence

Add a result object with:

- `kind`: `cash_positive`, `global_no_pay`, `scoped_no_pay`, `recognition_only`, `discretionary`, `third_party`, `historical`, or `unclear`.
- `sentence`: the sentence containing the evidence.
- `clause`: the clause containing the evidence.
- `subject`: `our_program`, `other_organization`, `researcher`, or `unknown`.
- `polarity`: `positive`, `negative`, or `conditional`.
- `scope`: `global`, `payment_method`, `severity`, `eligibility`, or `out_of_scope`.
- `time`: `current`, `historical`, `future`, or `unknown`.
- `payment_type`: `cash`, `cash_equivalent`, `non_cash`, or `unclear`.
- `amount`: normalized amount or range when present.
- `currency`: currency code or symbol when present.
- `current`: convenience boolean for `time=current`.
- `reason`: short explanation.

### 5.4 ScanResult

Add:

- `status`: one of the four statuses above.
- `label`: `PAID_BB`, `VDP`, `NOT_PROGRAM`, or `None`.
- `page_type`: page type result.
- `payment_status`: `paid`, `unpaid`, `unknown`, or `conflicting`.
- `requested_url` and `final_url`.
- `fetch_status`: HTTP status code or fetch error text for display; `PageContent.content_status` controls classification.
- `evidence`: payment evidence list.

Keep `confidence`, `decision_path`, `reward_candidates`, `first_party`, `reporting_channel_found`, `scope_found`, and `reasons`. Add new fields without removing old ones.

## 6. Fetch requirements

### 6.1 HTTP requests

Use a browser-like user agent by default, for example:

```text
Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36
```

Set at least:

- `User-Agent`
- `Accept: text/html,application/xhtml+xml,...`
- `Accept-Language: en-US,en;q=0.9`

Follow redirects and record the final URL. Platform detection must use the final URL. This matters for Bugcrowd's `/tesla` -> `/engagements/tesla` redirect.

Do not use a bot-style user agent for normal web pages. Mozilla returned 406 with the configured bot user agent during verification; a browser-like user agent returned 200. Network behaviour varies, so use the browser-like user agent and retry once with it before reporting the real fetch status.

### 6.2 Content extraction

Extract, in this order:

1. Visible main content from `main`, `article`, or `role="main"`, with navigation, header, footer, cookie banners, forms, scripts, and styles removed.
2. If no main region exists, the largest text-bearing body region.
3. Page title, meta description, Open Graph fields, Twitter card fields, canonical URL, and JSON-LD.

Do not discard useful metadata just because the visible body is empty. HackerOne, Google VRP, and Bugcrowd all need metadata or platform data.

Do not treat a large cookie banner or navigation block as the main content.

### 6.3 Thin and blocked pages

A page is `insufficient_content` when any of these is true and no platform resolver can provide program data:

- Visible text is shorter than 200 characters.
- The body is only a JavaScript-disabled notice, a login shell, a cookie wall, or an access-denied message.
- The response is a generic platform homepage even though the requested URL was a program URL.
- A browser fallback returns a thin or forbidden body after an initial 403/406/429.

An HTTP 403/406/429 with no usable fallback page is `fetch_error`, not `insufficient_content`. A page is not `NOT_PROGRAM` merely because it is thin or blocked. `NOT_PROGRAM` requires positive evidence that the page is not a program page.

### 6.4 security.txt

Fetch `/.well-known/security.txt` and `/security.txt` from the final URL origin.

Parse RFC 9116 fields. Use `Policy` and `Contact`:

- A `Policy` URL may be followed one hop when it is on the same registrable domain or on a known platform.
- A security-specific `Contact` can support a reporting channel.
- The mere presence of security.txt must add no program score and must not change a label by itself.
- A generic contact email such as `hello@` is not a vulnerability reporting channel.

The current +5 points for security.txt presence must be removed. Wikipedia's security.txt is a concrete false-positive source.

### 6.5 Browser fallback

Keep HTTP as the primary path. Use Playwright only when:

- the page is thin or blocked, and
- Playwright is installed, and
- the URL is a known JavaScript-heavy platform or an official page that is likely to render.

Do not make Playwright a hard dependency. If it is unavailable, return `insufficient_content` rather than guessing.

### 6.6 Platform resolvers

Platform resolvers are authoritative for specific program URLs. They bypass the pronoun requirement and the first-party score.

#### HackerOne

For `hackerone.com` URLs:

- Ignore platform-reserved paths such as `/`, `/bug-bounty-programs`, `/blog/`, `/customers`, `/product`, `/resources`, `/events`, `/about`, `/careers`, `/press`, `/legal`, `/terms`, `/privacy`, and `/leaderboard`.
- A path with one segment is a candidate program handle.
- Query `https://hackerone.com/graphql` with `team(handle: "<handle>")`.
- If the path is reserved, treat the page as non-program (directory/blog/homepage).
- If the path is a candidate handle and `team` is null, return `needs_review` or `insufficient_content`; a private program can also return null to anonymous requests. Do not return `NOT_PROGRAM` unless the page itself is clearly a directory, blog, or homepage.
- If `offers_bounties` is `true`, the program is `PAID_BB`.
- If `offers_bounties` is `false` and the team is public, the program is `VDP`.
- If the GraphQL request fails, fall back to metadata/HTML. If no program information remains, return `insufficient_content` or `needs_review`, not `NOT_PROGRAM`.

The resolver is optional infrastructure: it must not make the whole scan fail when HackerOne changes the endpoint.

#### Bugcrowd

For `bugcrowd.com` URLs:

- Specific program paths are `/engagements/<slug>` and the legacy `/<slug>` form.
- Directory paths such as `/engagements`, `/programs`, `/customers`, and `/` are non-program.
- Parse the embedded JSON in the HTML. The Tesla page contains `rewardAllocation: "pay_for_success"`.
- Treat `rewardAllocation: "pay_for_success"` as `PAID_BB`.
- If the embedded JSON has no reward allocation and the title/description explicitly says `VDP` or `Vulnerability Disclosure`, treat the page as `VDP`.
- If the title says `Bug Bounty` but there is no payment data, mark `needs_review` instead of guessing paid.
- If the field is present with an unknown value, mark `needs_review` instead of guessing.
- The page title "Bug Bounty: Tesla - Bugcrowd" and `og:description` "Tesla's Bug Bounty engagement" support official status but do not by themselves prove payment.

#### Intigriti

For `intigriti.com` program URLs:

- A specific program path is `/programs/<company>/<program>`.
- The app subdomain may return a forbidden page to anonymous requests.
- Use a public API or browser fallback if available.
- If neither works, return `insufficient_content`. Do not return `NOT_PROGRAM` for a known program URL that is merely inaccessible.

#### Google

For `bughunters.google.com` program pages:

- URL paths under `/about/rules/` and titles containing "Vulnerability Reward Program" or "VRP Rules" are official program pages.
- The official page metadata may be the only content available. Treat "potential reward amounts" on an official VRP rules page as payment evidence.
- Do not use this rule for generic Google marketing pages.

## 7. Page-type rules

Apply page type before payment.

### 7.1 Platform-specific program URL

If a known platform resolver identifies a specific program, set `page_type=official_program`.

Do not apply the company pronoun, domain-mention, or first-party score requirements to this page. The platform is the authority for the program.

### 7.2 Known non-program domains

Use a normalized host check. Fix the current denylist so entries match the normalization.

Do not use a naive last-two-labels function for multi-part public suffixes. For example, `crofting.scotland.gov.uk` must not become `gov.uk`, and `news.ycombinator.com` must still match a host rule. Match denylist entries against the exact host or a subdomain suffix of the entry. Use a small built-in suffix list only to compute the registrable domain for other checks. Cover at least `gov.uk`, `co.uk`, `org.uk`, `com.au`, and similar cases. Do not add a new dependency for this.

At minimum include or handle:

- News and blogs: `techcrunch.com`, `theverge.com`, `bleepingcomputer.com`, `arstechnica.com`, `wired.com`, `forbes.com`, `medium.com`, `reddit.com`, `news.ycombinator.com`, `krebsonsecurity.com`, `zdnet.com`, `thehackernews.com`, `securityweek.com`, `darkreading.com`, `infosecurity-magazine.com`.
- Reference and directory: `wikipedia.org`, `securitytxt.org`, `openbugbounty.org` directory pages.
- Platform non-program sections: the reserved HackerOne paths, Bugcrowd directory paths, and Intigriti directory paths listed above.

Do not hard-deny `bbradar.io` until its aggregator status is confirmed. Keep it as a conditional fixture; if confirmed, add it to the denylist and the fixture set together.

A denylist hit is `NOT_PROGRAM` only when it is a third-party or platform non-program page. A specific program page on a platform domain is not blocked by the platform's own denylist classification.

### 7.3 URL, title, and heading signals

An official company/government program page usually has at least two of these:

- URL path containing `security`, `security-policy`, `vulnerability-disclosure`, `vulnerability-reporting`, `bug-bounty`, `responsible-disclosure`, `vdp`, or `report-a-vulnerability`.
- Title or main heading containing `Vulnerability Disclosure Policy`, `Vulnerability Disclosure Program`, `Bug Bounty Program`, `Responsible Disclosure`, `Security Policy`, or `Report a vulnerability`.
- A clear invitation to report vulnerabilities.
- A scope, rules, or eligibility section.
- A security-specific reporting channel: `security@`, a vulnerability report form, a platform submission link, or a security.txt `Policy`/`Contact` pointer.
- Self-reference to the organization's own systems, products, or domains.

Do not require every signal. Do not require first-person pronouns.

### 7.4 Non-program signals

Use these as strong evidence that the page is not a program page:

- Title or heading such as `What is a bug bounty`, `Bug Bounty vs VDP`, `Top bug bounty programs`, `Best bug bounty platforms`, or `List of bug bounty programs`.
- Body content that lists many unrelated companies or programs.
- Calls to "browse programs", "compare programs", "find a program", or "view all programs".
- Wiki navigation, article metadata, author/date blocks, and citation markers.
- News/blog path prefixes such as `/news/`, `/blog/`, `/article/`, `/wiki/`, `/directory/`, `/programs/` when the domain is a news or directory site.
- Marketing copy about starting a program, with no scope or reporting channel for a specific program.
- Explicit closure: "the program has ended", "closed", or "no longer accepting reports" with no current reporting channel. Set `page_type=closed_program`.

`og:type=article` is a weak signal only. Official government pages can be articles (Finance NI and GOV.UK are examples). Do not reject on article metadata alone.

Do not reject a page only because its host contains `blog`. `mojdigital.blog.gov.uk` hosts an official policy page, while `hackerone.com/blog/` is a third-party platform blog. Use the host, path, title, and program evidence together.

### 7.5 Ambiguous pages

If the page is on an official-looking domain, contains program language, but lacks a clear page type, return `needs_review`. Do not default to `NOT_PROGRAM` and do not default to `PAID_BB`.

## 8. Payment-evidence rules

Replace the current bag-of-patterns classifier with a clause-level extractor.

### 8.1 Inputs

For each candidate sentence:

- Use the sentence itself and at most one adjacent sentence for antecedents.
- Split the sentence into clauses at `;`, `, but`, `, however`, `, although`, and sentence boundaries.
- Classify each clause that contains a reward, payment, bounty, compensation, recognition, or cash term.
- Keep the exact sentence and clause in the evidence output.

Do not let a monetary term in an unrelated clause override a no-pay clause in the same window.

### 8.2 Clause attributes

For each clause, determine:

- Subject: `our_program`, `other_organization`, `researcher`, or `unknown`.
- Polarity: positive, negative, or conditional.
- Scope: global, payment-method, severity, eligibility, or out-of-scope.
- Time: current, historical, future, or unknown.
- Type: cash, cash-equivalent, non-cash recognition, or unclear.

### 8.3 Positive cash evidence

Treat a clause as positive cash evidence only when all of these hold:

- The subject is the program operator, not another company and not a researcher.
- The statement is current.
- The clause contains cash, a cash-equivalent payment mechanism, or a stated monetary amount/range.
- The clause is not negated for the whole program.

Examples:

- "We pay bounties up to $5,000."
- "Rewards range from $500 to $10,000."
- "We offer cash rewards for critical vulnerabilities."
- "Bounty payments are made by bank transfer."
- "We pay via PayPal."
- "Rewards are paid in USD."

Platform fields such as HackerOne `offers_bounties: true` and Bugcrowd `rewardAllocation: pay_for_success` are authoritative positive evidence.

Documented platform exception: an official Google VRP rules page whose title or metadata explicitly describes a reward program and "potential reward amounts" counts as positive cash evidence even when the number is not in the fetched text. Do not generalise this exception to other sites; it applies only to recognised official Google VRP rules pages.

### 8.4 Global no-pay evidence

Treat a clause as global no-pay only when it denies payment for the whole program.

Support at least these forms:

- `we do not offer monetary rewards`
- `we do not offer cash bounties`
- `we do not pay bounties`
- `this program does not provide monetary compensation`
- `you will not be paid a reward`
- `no bug bounty program`
- `not a paid bug bounty`
- `unpaid`
- `non-monetary`
- `we no longer offer any monetary reward`
- `it is not currently possible for us to offer a paid bug bounty`

Do not treat these as global no-pay:

- `we do not pay for low-severity reports` (scope: severity)
- `we do not pay for out-of-scope assets` (scope: eligibility)
- `we do not pay via PayPal` (scope: payment method)
- `we do not pay for informational findings` (scope: severity)

### 8.5 Subject attribution

Ignore reward statements about someone else:

- "Other companies pay up to $50,000."
- "Researchers earned $2 million last year."
- "Another company's program pays..."
- "According to the report, the vendor paid..."

On a third-party page, these statements are not evidence for the page's own program. On an official page, "the company" or "the organization" may refer to the page owner; use the domain, title, and surrounding context before treating it as third party. On an official page, background mentions of other companies or past researcher earnings are not a current commitment.

### 8.6 Time handling

- Present-tense commitments such as "we pay", "we offer", and "rewards range" are current.
- Past-tense statements such as "we paid", "we used to offer", and "researchers earned" are not current.
- Explicit end markers such as "no longer", "ended", "previous program", and "program closed" are not current.
- "We no longer offer a paid bounty, but we still accept reports" is VDP.
- "The program has ended and we no longer accept reports" is `NOT_PROGRAM`.

### 8.7 Recognition and non-cash rewards

Treat these as VDP evidence, not paid evidence:

- Hall of Fame
- public credit or acknowledgment
- swag
- gift cards
- points, credits, discounts
- "token of appreciation"
- "unique reward" with no cash amount or cash mechanism

A page that says "We do not offer monetary rewards, however, reporters may receive a unique reward" is VDP unless a separate current clause clearly states cash payment.

### 8.8 Conflicting evidence

Resolve conflicts with these rules:

- A current, global no-pay statement wins over a historical, third-party, or scoped positive.
- A current global cash clause wins over a scoped no-pay clause.
- A current global no-pay plus a current global cash clause for the same program is `needs_review`, not an automatic `PAID_BB`.
- Scoped cash evidence does not override a current global no-pay. Scoped no-pay evidence does not override current global cash.
- A page with only recognition language is VDP.
- A page with no payment language but an official program page is VDP.
- If one page describes multiple programs, classify the program named by the URL, title, or main heading. If the page cannot be tied to one program and contains both a paid and an unpaid program, return `needs_review`; do not label the whole page `PAID_BB`.

## 9. Decision table

Use this order. The first matching rule wins, and `decision_path` must name the rule.

Only current **global** evidence participates in the payment rules. Scoped evidence is retained in `evidence` but does not change the global decision.

1. `content_status=fetch_error` -> status `fetch_error`; label `None`.
2. `content_status=insufficient_content` -> status `insufficient_content`; label `None`.
3. `page_type` is `closed_program`, `news`, `blog`, `wiki`, `directory`, `aggregator`, `marketing`, or `generic_security` -> `NOT_PROGRAM`; path `page_type_non_program`.
4. `page_type=unknown` -> status `needs_review`; label `None`; path `page_type_needs_review`.
5. `page_type=official_program` and page cannot be tied to one program and contains both current paid and unpaid programs -> status `needs_review`; path `multi_program_ambiguous`.
6. `page_type=official_program` and current global no-pay and not current global cash -> `VDP`; path `official_program_global_no_pay`.
7. `page_type=official_program` and current global cash and not current global no-pay -> `PAID_BB`; path `official_program_current_cash`.
8. `page_type=official_program` and current global no-pay and current global cash -> status `needs_review`; path `official_program_conflicting_payment`.
9. `page_type=official_program` and recognition-only or no payment evidence -> `VDP`; path `official_program_no_cash`.
10. Otherwise -> status `needs_review`; path `fallthrough_needs_review`.

Do not use `NOT_PROGRAM` as the fallthrough for unknown pages. A closed program with no current reporting channel is `NOT_PROGRAM`; a closed paid program that still accepts reports is `VDP` and must not be classified as `closed_program`.

## 10. First-party scoring changes

Retain the score for explainability, but stop using it as a gate.

Required changes:

- Remove the entire `_structural_reject` gate. Do not replace it with another pronoun-or-channel requirement. A missing channel can lower confidence or send the page to `needs_review`; it must not automatically produce `NOT_PROGRAM`.
- Remove security.txt presence points.
- Count only security-specific reporting channels, not any email address.
- Prefer `main`/`article` content so cookie banners and navigation do not inflate pronoun or domain counts.
- Add a negative signal for obvious article/list/directory structure, but do not make it decisive.
- For platform program pages, mark first-party scoring as not applicable instead of penalizing the page.
- If the score is used at all, use it only as a tie-breaker between two official program pages or as part of confidence. It must not prevent a VDP or paid program from being recognized.

The current `high_threshold: 15` is too low and is the reason Wikipedia passes. Do not simply raise it; replace the gate.

## 11. Implementation guidance

Suggested modules:

- `core/fetcher.py`: browser-like request, metadata, final URL, content status.
- `core/page_type.py`: page-type classification and platform dispatch.
- `core/platforms.py`: HackerOne GraphQL, Bugcrowd embedded JSON, Intigriti/Google handling.
- `core/payment_evidence.py`: clause-level evidence extraction.
- `core/decision_engine.py`: statuses, page type, payment status.
- `core/first_party.py`: supporting signals only.
- `core/models.py`: new dataclasses and statuses.
- `config/reward_patterns.yaml`: replace malformed monetary patterns; remove `gift card` from cash patterns.
- `config/domains_denylist.yaml`: expand and normalize.

Keep the existing CLI and Python API working. Add fields to `ScanResult`; do not remove existing fields. `Pipeline.run_from_page` must remain usable for offline fixtures.

Suggested implementation order:

1. Fix fetch user agent, metadata, final URL, and content-status handling.
2. Add page-type classification and platform resolvers.
3. Add clause-level payment evidence and remove the monetary-first classifier order.
4. Add the new decision table and statuses.
5. Update first-party scoring to supporting evidence only.
6. Add fixtures and tests.
7. Update README and CLI output.

Do not add new runtime dependencies. Playwright remains optional.

## 12. Test plan

The README describes a test suite, but the repository currently has no `tests/` directory. Add one. Do not rely on live network requests in the normal test run.

### 12.1 Unit tests

Add tests for payment evidence:

- Positive: `We pay bounties up to $5,000.`
- Positive: `Rewards range from $500 to $10,000.`
- Positive: `We pay via bank transfer.`
- Positive: `We do not pay via PayPal; we pay via bank transfer.`
- Positive: `We do not pay for low-severity findings; we pay up to $10,000 for critical issues.`
- Negative global: `We do not offer monetary rewards.`
- Negative global: `You will not be paid a reward for reporting a vulnerability.`
- Negative global: `It is not currently possible for us to offer a paid bug bounty programme.`
- Negative scoped: `We do not pay for low-severity reports.`
- Negative scoped: `We do not pay via PayPal.`
- Historical: `We no longer offer a paid bug bounty, but we still accept reports.`
- Historical: `We used to offer cash rewards.`
- Third party: `Other companies pay up to $50,000.`
- Third party: `Researchers earned $2 million last year.`
- Non-cash: `We offer swag for valid reports.`
- Non-cash: `We list researchers in our Hall of Fame.`
- Non-cash: `We do not offer gift cards.`
- Contradiction: current global no-pay plus current global cash payment -> `needs_review`.
- Scoped no-pay plus current global cash -> `PAID_BB`.
- Global no-pay plus scoped cash -> `VDP`.
- A page with one paid program and one VDP with no way to tell which one the URL refers to -> `needs_review`.

Add tests for page type:

- HackerOne specific program page -> official program.
- HackerOne `/bug-bounty-programs` -> directory.
- HackerOne `/blog/...` -> blog.
- Wikipedia -> wiki.
- HackerOne homepage -> non-program.
- Finance NI article page -> official program.
- GOV.UK article page -> official program.
- News article with dollar amounts -> non-program.
- Generic company security contact page with no scope or reporting process -> non-program.
- Closed program with no current reporting channel -> `closed_program` and `NOT_PROGRAM`.
- Closed paid program that still accepts reports -> `VDP`, not `closed_program`.
- Thin JavaScript shell -> insufficient content.

Add tests for fetch:

- Browser-like user agent is sent.
- Redirect final URL is recorded.
- Meta title/description/OG/JSON-LD are captured.
- Empty body plus useful meta is not treated as a fetch failure.
- Thin body plus no meta is insufficient content.
- security.txt fields are parsed.
- security.txt presence alone does not change the label.
- Generic email is not a vulnerability reporting channel.

Add tests for platform resolvers:

- Mock HackerOne GraphQL `offers_bounties: true`.
- Mock HackerOne GraphQL `offers_bounties: false`.
- Mock missing HackerOne team.
- Mock Bugcrowd `rewardAllocation: pay_for_success`.
- Mock unknown Bugcrowd reward allocation.
- Mock Intigriti forbidden response -> insufficient content.

### 12.2 Golden fixtures

Store representative HTML/meta/JSON fixtures under `tests/fixtures/`. Each fixture should have:

- `page.html`
- `meta.json` when needed
- `security.txt` when needed
- `expected.json` with label, status, page type, payment status, and decision path

Minimum fixture set:

Paid:

- HackerOne `/security`
- Google VRP rules page
- Mozilla security bug bounty page
- Bugcrowd Tesla page
- Microsoft MSRC bounty
- Apple Security Bounty
- Palo Alto Networks bug bounty
- Nym VDP/BBP (current paid result verified)

VDP:

- DHS vulnerability disclosure policy
- GOV.UK report-vulnerability page
- MOJ Digital vulnerability disclosure policy
- Finance NI vulnerability disclosure page
- Cyble security disclosure policy
- Crofting vulnerability disclosure policy
- Good Penguin vulnerability disclosure policy
- ReadyTech vulnerability disclosure page
- Grand Challenge vulnerability disclosure page
- BBC Backstage security disclosure policy
- FCDO vulnerability reporting page

Not program:

- Wikipedia bug bounty article
- HackerOne bug bounty programs directory
- HackerOne blog post
- HackerOne homepage
- securitytxt.org
- One news article about a paid program
- One generic marketing page about bug bounties

Insufficient content / fetch error:

- Intigriti program page when anonymous access is forbidden
- A 403 page
- A thin JavaScript shell with no metadata

Conditional fixtures:

- LOD vulnerability disclosure policy: `VDP` if browser-rendered content is available; otherwise `insufficient_content`.
- ISC defect and vulnerability disclosure policy: `VDP` or `needs_review`. The page says "No Bounties" but also mentions a European Commission-funded one-year BIND bug bounty. It must not return `NOT_PROGRAM`.
- bbradar program/listing page: `NOT_PROGRAM` only after its aggregator status is confirmed; otherwise `needs_review`.
- Upplc disclosure page: `fetch_error` or `insufficient_content` while it returns HTTP 403.

Do not include conditional fixtures in the strict pass/fail set until their ground truth is recorded. Do not commit full copies of pages that contain secrets, tokens, or personal data. Remove cookies, CSRF values, and unrelated scripts from fixtures.

### 12.3 Acceptance criteria

With the fixture set and mocked platform responses:

- Every deterministic paid fixture returns `PAID_BB`.
- Every deterministic VDP fixture with accessible content returns `VDP`.
- Every deterministic non-program fixture returns `NOT_PROGRAM`.
- Every blocked/thin fixture returns `insufficient_content` or `fetch_error`, never `NOT_PROGRAM`.
- No fixture containing only a third-party article or directory returns `PAID_BB`.
- No fixture with an explicit global no-pay statement returns `PAID_BB`.
- No fixture with a scoped no-pay statement and a current positive cash clause returns `VDP` solely because of the scoped no-pay.
- Mozilla's fixture is classified without a 406 error.
- HackerOne `/security` is classified as `PAID_BB` via the platform resolver even when its body is a JavaScript shell.
- HackerOne `/bug-bounty-programs` remains `NOT_PROGRAM` even though it contains program listings and dollar amounts.
- Wikipedia remains `NOT_PROGRAM` even though it has a valid security.txt.
- Finance NI remains `VDP` even though its page has `og:type=article`.

Targets for the curated fixture set:

- `PAID_BB` recall: 1.0.
- `VDP` recall: 1.0.
- `NOT_PROGRAM` precision: 1.0.
- No known false paid result on a non-program fixture.
- No known `NOT_PROGRAM` result on an official program fixture.

For live integration tests, report results separately. Do not make live network behavior a release blocker.

## 13. Acceptance examples

| URL | Expected result | Reason |
|---|---|---|
| `https://hackerone.com/security` | `PAID_BB` | HackerOne GraphQL `offers_bounties=true` |
| `https://bughunters.google.com/about/rules/google-friends/google-and-alphabet-vulnerability-reward-program-vrp-rules` | `PAID_BB` | Official Google VRP rules with reward amounts |
| `https://www.mozilla.org/en-US/security/bug-bounty/` | `PAID_BB` | Official Mozilla bounty page, browser-like fetch |
| `https://bugcrowd.com/tesla` | `PAID_BB` | Bugcrowd embedded JSON `rewardAllocation=pay_for_success` |
| `https://www.microsoft.com/en-us/msrc/bounty` | `PAID_BB` | Official paid program |
| `https://security.apple.com/bounty/` | `PAID_BB` | Official paid program |
| `https://security.paloaltonetworks.com/bugbounty` | `PAID_BB` | Official paid program |
| `https://www.dhs.gov/vulnerability-disclosure-policy` | `VDP` | Official disclosure policy, no cash reward |
| `https://www.gov.uk/help/report-vulnerability` | `VDP` | Official disclosure page, explicitly no reward |
| `https://mojdigital.blog.gov.uk/vulnerability-disclosure-policy` | `VDP` | Official policy, no cash reward |
| `https://www.lodlaw.com/legal-disclosures/vulnerability-disclosure-policy` | `VDP` or insufficient content | Official path; use browser if needed |
| `https://www.finance-ni.gov.uk/articles/vulnerability-disclosure` | `VDP` | Official policy, article metadata is not decisive |
| `https://cyble.com/security-disclosure-policy` | `VDP` | Explicitly no monetary rewards |
| `https://www.crofting.scotland.gov.uk/vulnerability-disclosure-policy` | `VDP` | Explicitly no monetary rewards |
| `https://www.thegoodpenguin.co.uk/Vulnerability-Disclosure-Policy` | `VDP` | Explicitly no monetary rewards |
| `https://readytech.io/vulnerability-disclosure` | `VDP` | Explicitly no monetary rewards |
| `https://grand-challenge.org/vulnerability-disclosure` | `VDP` | Explicitly no monetary compensation |
| `https://www.bbc.co.uk/backstage/security-disclosure-policy/` | `VDP` | Explicitly no paid bounty |
| `https://www.fcdoservices.gov.uk/vulnerability-reporting` | `VDP` | Explicitly no paid bounty |
| `https://kb.isc.org/docs/aa-00861` | `VDP` or `needs_review` | "No Bounties" conflicts with a footnote about an EC-funded BIND bounty |
| `https://en.wikipedia.org/wiki/Bug_bounty_program` | `NOT_PROGRAM` | Wiki article, not an official program |
| `https://www.hackerone.com/bug-bounty-programs` | `NOT_PROGRAM` | Platform directory |
| `https://www.hackerone.com/blog/bug-bounty-vs-vdp-which-program-right-you` | `NOT_PROGRAM` | Blog article |
| `https://www.hackerone.com/` | `NOT_PROGRAM` | Platform homepage |
| `https://securitytxt.org/` | `NOT_PROGRAM` | Informational site, not a program |
| `https://www.intigriti.com/programs/intigriti/intigriti-bug-bounty` | `insufficient_content` if anonymous access fails | Known program URL, blocked page |
| `https://upplc.com/vulnerability-disclosure-policy/` | `fetch_error` or insufficient content | HTTP 403 |

Conditional cases are not strict release blockers. They must not return a wrong confident label (`NOT_PROGRAM` for a known program or `PAID_BB` without cash evidence). Record their ground truth in `expected.json` before adding them to the strict set.

## 14. Risks and limits

- Platform APIs and embedded JSON can change without notice. Resolvers must fail closed to `insufficient_content` or `needs_review`, never to a guessed label.
- Metadata can be stale or marketing copy. Use it as supporting evidence, not as the only signal for a generic page.
- The cash-versus-non-cash rule is a product decision. It is deliberately conservative: gift cards, swag, and recognition are VDP.
- Some official pages are JavaScript-only or block anonymous requests. An honest insufficient-content result is better than a false `NOT_PROGRAM` or `PAID_BB`.
- A denylist will never cover every third-party site. Page-type content rules and URL patterns must carry most of the weight.
- The classifier remains rule-based. New phrasing may require new patterns and fixtures, but the evidence model must stay explainable.

## 15. Definition of done

The change is complete when:

- The fetch path uses a browser-like user agent, records final URLs, and treats a Mozilla 406 as a fetch error rather than `NOT_PROGRAM`.
- HackerOne and Bugcrowd program pages resolve through platform data or explicit platform metadata.
- The pipeline no longer requires first-person pronouns to recognize an official policy page.
- Clause-level evidence correctly handles global negation, scoped negation, subject attribution, and historical statements.
- The decision table uses page type before payment and never uses `NOT_PROGRAM` as an error fallthrough.
- `security.txt` presence no longer creates a program score.
- The fixture suite passes the acceptance cases above.
- The CLI and Python API remain usable, with statuses and labels documented.
