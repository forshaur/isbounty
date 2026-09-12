"""Page retrieval + cleaning.

Primary path: headless browser (Playwright) so JS-rendered content is
captured. Falls back to plain requests if the browser path fails for any
reason (not installed, launch error, navigation timeout, etc).

Produces a PageContent object: cleaned text, sentence list, headings,
registrable domain, and (if present) security.txt content.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from .models import PageContent
from .text_utils import split_sentences
from ..utils.logging import get_logger

log = get_logger(__name__)

_STRIP_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]


def _clean_html(html: str) -> tuple[str, list[str]]:
    """Strip boilerplate, find the largest coherent text region, return
    (clean_text, headings). This is a lightweight readability approximation:
    among body's direct text-bearing descendants, pick the one with the
    most visible text, rather than a full boilerplate-removal library."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]

    candidates = soup.find_all(["main", "article", "div", "section", "body"])
    best = max(candidates, key=lambda t: len(t.get_text(strip=True)), default=soup)
    text = best.get_text("\n", strip=True) if best else soup.get_text("\n", strip=True)
    return text, headings


def _fetch_via_browser(url: str, timeout_ms: int) -> str | None:
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
                html = page.content()
                return html
            finally:
                browser.close()
    except Exception as e:  # noqa: BLE001 - any browser failure -> fallback
        log.warning(f"browser fetch failed for {url}: {e}")
        return None


def _fetch_via_http(url: str, timeout_s: int, user_agent: str) -> str:
    resp = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout_s)
    resp.raise_for_status()
    return resp.text


def _fetch_security_txt(url: str, timeout_s: int, user_agent: str) -> str | None:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in ("/.well-known/security.txt", "/security.txt"):
        try:
            resp = requests.get(urljoin(base, path),
                                 headers={"User-Agent": user_agent}, timeout=timeout_s)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text.strip()
        except requests.RequestException:
            continue
    return None


def registrable_domain(netloc: str) -> str:
    host = netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def fetch_page(url: str, timeout_seconds: int = 15,
                user_agent: str = "Mozilla/5.0 (compatible; BBScanner/1.0)",
                use_browser_rendering: bool = True) -> PageContent:
    html = None
    if use_browser_rendering:
        html = _fetch_via_browser(url, timeout_ms=timeout_seconds * 1000)
    if html is None:
        html = _fetch_via_http(url, timeout_seconds, user_agent)

    text, headings = _clean_html(html)
    sentences = split_sentences(text)
    domain = registrable_domain(urlparse(url).netloc)
    security_txt = _fetch_security_txt(url, timeout_seconds, user_agent)

    return PageContent(
        url=url, raw_text=text, sentences=sentences, headings=headings,
        domain=domain, security_txt=security_txt,
    )
