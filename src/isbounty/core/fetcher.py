"""Page retrieval, metadata extraction and cleaning.

Primary path is a browser-like HTTP request. Playwright is an optional
fallback for thin or blocked pages; it is never a hard dependency.

Produces a PageContent object with visible text, sentences, headings,
metadata, JSON-LD, the final URL after redirects, security.txt fields and
an operational content_status.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from .models import (
    CONTENT_FETCH_ERROR,
    CONTENT_INSUFFICIENT,
    CONTENT_OK,
    PageContent,
)
from .text_utils import split_sentences
from ..utils.logging import get_logger

log = get_logger(__name__)

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
_ACCEPT_LANGUAGE = "en-US,en;q=0.9"

_STRIP_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]
_BOILERPLATE_RE = re.compile(
    r"cookie|consent|gdpr|banner|navbar|navigation|menu|masthead|sidebar|breadcrumb",
    re.IGNORECASE,
)
_THIN_NOTICE_RE = re.compile(
    r"enable javascript|javascript is disabled|requires javascript|"
    r"sign in to continue|log in to continue|please log in|access denied|"
    r"forbidden|403 forbidden|are you a robot|captcha|checking your browser",
    re.IGNORECASE,
)
_BLOCKED_STATUSES = {403, 406, 429}

# Small built-in suffix list. No new dependency; enough to compute a
# registrable domain without collapsing crofting.scotland.gov.uk to gov.uk.
_MULTI_PART_SUFFIXES = {
    "gov.uk", "co.uk", "org.uk", "ac.uk", "me.uk", "ltd.uk", "plc.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au", "co.nz", "net.nz",
    "org.nz", "govt.nz", "co.jp", "or.jp", "ne.jp", "ac.jp", "go.jp",
    "co.in", "net.in", "org.in", "gov.in", "com.br", "net.br", "org.br",
    "co.za", "org.za", "gov.za", "com.sg", "edu.sg", "gov.sg",
    "com.mx", "com.tr", "com.cn", "com.hk", "com.tw",
}


def registrable_domain(netloc: str) -> str:
    """Return the registrable domain using a small public-suffix subset."""
    host = (netloc or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) <= 1:
        return host
    last_two = ".".join(parts[-2:])
    if last_two in _MULTI_PART_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def host_matches(host: str, entry: str) -> bool:
    """Exact host or subdomain-suffix match, never a naive last-two split."""
    host = (host or "").lower().strip(".")
    entry = (entry or "").lower().strip(".")
    return host == entry or host.endswith("." + entry)


def parse_security_txt(text: str) -> dict:
    """Parse RFC 9116 fields into a lowercase-keyed dict of value lists."""
    fields: dict[str, list[str]] = {}
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if not key or not value:
            continue
        fields.setdefault(key, []).append(value)
    return fields


def _extract_metadata(soup: BeautifulSoup | str) -> tuple[dict, list[dict]]:
    if isinstance(soup, str):
        soup = BeautifulSoup(soup, "html.parser")
    metadata: dict = {"open_graph": {}, "twitter_card": {}}
    if soup.title and soup.title.string:
        metadata["title"] = soup.title.string.strip()

    for tag in soup.find_all("meta"):
        name = (tag.get("name") or tag.get("property") or "").strip().lower()
        content = (tag.get("content") or "").strip()
        if not name or not content:
            continue
        if name in ("description", "og:description", "twitter:description"):
            metadata.setdefault("description", content)
        if name.startswith("og:"):
            metadata["open_graph"][name[3:]] = content
            metadata[name.replace(":", "_")] = content
        elif name.startswith("twitter:"):
            metadata["twitter_card"][name[8:]] = content
            metadata[name.replace(":", "_")] = content
        else:
            metadata[name] = content

    canonical = soup.find("link", rel=lambda v: v and "canonical" in v)
    if canonical and canonical.get("href"):
        metadata["canonical"] = canonical["href"].strip()

    json_ld: list[dict] = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if isinstance(data, list):
            json_ld.extend(x for x in data if isinstance(x, dict))
        elif isinstance(data, dict):
            json_ld.append(data)
    return metadata, json_ld


def _clean_html(html: str) -> tuple[str, list[str], BeautifulSoup]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    for tag in soup.find_all(True):
        ident = " ".join(
            str(tag.get(attr, "")) for attr in ("id", "class", "role", "aria-label")
        )
        if ident and _BOILERPLATE_RE.search(ident):
            tag.decompose()

    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]

    main = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"})
    if main and len(main.get_text(" ", strip=True)) >= 40:
        best = main
    else:
        candidates = soup.find_all(["div", "section", "article", "body"])
        best = max(
            candidates,
            key=lambda t: len(t.get_text(strip=True)),
            default=soup,
        )
    text = best.get_text("\n", strip=True) if best else soup.get_text("\n", strip=True)
    return text, headings, soup


def _fetch_via_browser(url: str, timeout_ms: int) -> tuple[str, str] | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.info("playwright not installed, skipping browser fetch")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(url, timeout=timeout_ms, wait_until="networkidle")
                return page.content(), page.url
            finally:
                browser.close()
    except Exception as e:  # noqa: BLE001 - any browser failure -> fallback
        log.warning(f"browser fetch failed for {url}: {e}")
        return None


def _http_get(url: str, timeout_s: int, user_agent: str):
    headers = {
        "User-Agent": user_agent,
        "Accept": _ACCEPT,
        "Accept-Language": _ACCEPT_LANGUAGE,
    }
    return requests.get(url, headers=headers, timeout=timeout_s, allow_redirects=True)


def _fetch_security_txt(final_url: str, timeout_s: int, user_agent: str) -> str | None:
    parsed = urlparse(final_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    base = f"{parsed.scheme}://{parsed.netloc}"
    headers = {"User-Agent": user_agent, "Accept": "text/plain,*/*"}
    for path in ("/.well-known/security.txt", "/security.txt"):
        try:
            resp = requests.get(urljoin(base, path), headers=headers, timeout=timeout_s)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text.strip()
        except requests.RequestException:
            continue
    return None


def _looks_blocked(text: str) -> bool:
    if not text:
        return True
    return len(text.strip()) < 200 or bool(_THIN_NOTICE_RE.search(text[:4000]))


def _empty(url: str, error: str, status_code: int | None = None,
           final_url: str | None = None) -> PageContent:
    final_url = final_url or url
    host = (urlparse(final_url).hostname or "").lower()
    return PageContent(
        url=url,
        requested_url=url,
        final_url=final_url,
        raw_text="",
        sentences=[],
        headings=[],
        domain=registrable_domain(host),
        host=host,
        status_code=status_code,
        fetch_error=error,
        content_status=CONTENT_FETCH_ERROR,
    )


def fetch_page(url: str, timeout_seconds: int = 15,
               user_agent: str = BROWSER_USER_AGENT,
               use_browser_rendering: bool = False) -> PageContent:
    """Fetch a URL and return PageContent. Never raises for HTTP failures.

    A 403/406/429 is retried once with the browser-like user agent. If that
    still fails and no usable browser fallback exists it is fetch_error, not
    NOT_PROGRAM.
    """
    html: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    final_url = url
    fetch_error: str | None = None
    response = None

    try:
        response = _http_get(url, timeout_seconds, user_agent)
        status_code = response.status_code
        final_url = response.url or url
        content_type = response.headers.get("content-type", "")
        if status_code in _BLOCKED_STATUSES:
            retry_agent = (
                user_agent if "Mozilla" in user_agent else BROWSER_USER_AGENT
            )
            response = _http_get(url, timeout_seconds, retry_agent)
            status_code = response.status_code
            final_url = response.url or final_url
            content_type = response.headers.get("content-type", "")
        if status_code >= 400:
            fetch_error = f"HTTP {status_code}"
            html = response.text if status_code in _BLOCKED_STATUSES else None
        else:
            html = response.text
    except requests.RequestException as e:
        fetch_error = str(e)

    rendered = False
    if (html is None or _looks_blocked(html)) and use_browser_rendering:
        browser_result = _fetch_via_browser(url, timeout_ms=timeout_seconds * 1000)
        if browser_result:
            html, final_url = browser_result
            fetch_error = None
            status_code = None
            rendered = True

    if html is None:
        return _empty(url, fetch_error or "empty response", status_code, final_url)

    metadata, json_ld = _extract_metadata(html)
    text, headings, soup = _clean_html(html)

    if use_browser_rendering and not rendered and _looks_blocked(text):
        browser_result = _fetch_via_browser(url, timeout_ms=timeout_seconds * 1000)
        if browser_result:
            html, final_url = browser_result
            fetch_error = None
            status_code = None
            metadata, json_ld = _extract_metadata(html)
            text, headings, soup = _clean_html(html)
    host = (urlparse(final_url).hostname or "").lower()
    security_txt = _fetch_security_txt(final_url, timeout_seconds, user_agent)
    fields = parse_security_txt(security_txt) if security_txt else {}

    if status_code is not None and status_code >= 400:
        # A blocked status with a usable fallback body is still an inadequate
        # page unless the body actually carries content.
        content_status = CONTENT_OK if not _looks_blocked(text) else CONTENT_FETCH_ERROR
    elif _looks_blocked(text):
        content_status = CONTENT_INSUFFICIENT
    else:
        content_status = CONTENT_OK

    return PageContent(
        url=url,
        requested_url=url,
        final_url=final_url,
        raw_text=text,
        sentences=split_sentences(text),
        headings=headings,
        domain=registrable_domain(host),
        host=host,
        status_code=status_code,
        content_type=content_type,
        metadata=metadata,
        json_ld=json_ld,
        fetch_error=fetch_error,
        content_status=content_status,
        security_txt=security_txt,
        security_txt_fields=fields,
        raw_html=html,
    )
