"""Resilient web-knowledge layer: one snippet source, many providers.

Enrichment needs short factual web snippets (baggage fees, student discounts,
allowances). Instead of calling Serper directly, callers use
:func:`get_web_snippets`, which tries a chain of providers and returns the first
non-empty result:

1. **Serper** — fast paid API (skipped while a circuit breaker cools it down).
2. **DuckDuckGo** — keyless HTML endpoint over httpx (no browser).
3. **Playwright** — headless Chromium; robust against JS, lazily imported and
   auto-disabled when the package/browser is unavailable.

All providers share the same ``list[str]`` ("title - snippet") contract, so the
LLM extractors never change. When every provider fails we return ``[]`` and the
caller degrades gracefully (no hallucinated data). A module-level status records
which provider served the last call, for pipeline logging.
"""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional, Union
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.tools.serper import web_search_documents

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_log = get_logger("tools.web_knowledge")


@dataclass(frozen=True)
class WebSnippet:
    """One search result: its ``title - snippet`` text and source URL."""

    text: str
    url: str = ""

    @property
    def domain(self) -> str:
        try:
            host = urlparse(self.url).netloc.lower()
        except Exception:
            return ""
        return host[4:] if host.startswith("www.") else host


@dataclass
class _Health:
    """Circuit-breaker state for one provider."""

    unhealthy_until: float = 0.0

    def available(self) -> bool:
        return time.time() >= self.unhealthy_until

    def trip(self, cooldown: int) -> None:
        self.unhealthy_until = time.time() + cooldown


@dataclass
class _Status:
    """Which provider served the most recent successful call (for logging)."""

    provider: Optional[str] = None
    all_failed: bool = False


_HEALTH: dict[str, _Health] = {"serper": _Health(), "duckduckgo": _Health(), "playwright": _Health()}
_STATUS = _Status()
# Set to False by tests when a browser is not installed; probed lazily otherwise.
_PLAYWRIGHT_AVAILABLE: Optional[bool] = None


def last_status() -> _Status:
    """Return the provider that served the last :func:`get_web_snippets` call."""

    return _Status(provider=_STATUS.provider, all_failed=_STATUS.all_failed)


def reset_status() -> None:
    """Clear the served-provider status (call before a batch of lookups)."""

    _STATUS.provider = None
    _STATUS.all_failed = False


def reset_health() -> None:
    """Clear circuit-breaker state (used by tests)."""

    for h in _HEALTH.values():
        h.unhealthy_until = 0.0


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
def _serper_search(query: str, num: int, settings: Settings) -> list[WebSnippet]:
    docs = web_search_documents(query, num=num, settings=settings, timeout=settings.web_search_timeout)
    return [WebSnippet(text, url) for text, url in docs]


_DDG_RESULT_RE = re.compile(
    r'result__a[^>]*href="(?P<url>[^"]*)"[^>]*>(?P<title>.*?)</a>.*?result__snippet[^>]*>(?P<snippet>.*?)</a>',
    re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text)).strip()


def _ddg_real_url(href: str) -> str:
    """Resolve a DuckDuckGo redirect (``/l/?uddg=<encoded>``) to the real URL."""

    href = html.unescape(href or "")
    if href.startswith("//"):
        href = "https:" + href
    try:
        params = parse_qs(urlparse(href).query)
        if "uddg" in params:
            return unquote(params["uddg"][0])
    except Exception:
        pass
    return href


def _duckduckgo_search(query: str, num: int, settings: Settings) -> list[WebSnippet]:
    """Keyless DuckDuckGo HTML search; parse result titles, snippets + URLs."""

    resp = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": _UA},
        timeout=settings.web_search_timeout,
        follow_redirects=True,
    )
    resp.raise_for_status()
    snippets: list[WebSnippet] = []
    for m in _DDG_RESULT_RE.finditer(resp.text):
        title = _strip_html(m.group("title"))
        snippet = _strip_html(m.group("snippet"))
        if snippet:
            text = f"{title} - {snippet}" if title else snippet
            snippets.append(WebSnippet(text, _ddg_real_url(m.group("url"))))
        if len(snippets) >= num:
            break
    return snippets


def _playwright_available() -> bool:
    global _PLAYWRIGHT_AVAILABLE
    if _PLAYWRIGHT_AVAILABLE is not None:
        return _PLAYWRIGHT_AVAILABLE
    try:
        import playwright.sync_api  # noqa: F401

        _PLAYWRIGHT_AVAILABLE = True
    except Exception:
        _PLAYWRIGHT_AVAILABLE = False
    return _PLAYWRIGHT_AVAILABLE


def _playwright_search(query: str, num: int, settings: Settings) -> list[WebSnippet]:
    """Headless-Chromium DuckDuckGo search; robust against JS-gated pages."""

    from playwright.sync_api import sync_playwright

    snippets: list[WebSnippet] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=_UA)
            # Speed: skip images/fonts/media we never read.
            context.route(
                re.compile(r"\.(png|jpg|jpeg|gif|webp|svg|woff2?|ttf|mp4|css)$"),
                lambda route: route.abort(),
            )
            page = context.new_page()
            page.goto(
                f"https://duckduckgo.com/html/?q={httpx.QueryParams({'q': query})['q']}",
                timeout=int(settings.web_search_timeout * 1000),
                wait_until="domcontentloaded",
            )
            for res in page.query_selector_all(".result")[:num]:
                snip_el = res.query_selector(".result__snippet")
                text = (snip_el.inner_text() if snip_el else "") or ""
                text = text.strip()
                if not text:
                    continue
                anchor = res.query_selector(".result__a")
                href = anchor.get_attribute("href") if anchor else ""
                snippets.append(WebSnippet(text, _ddg_real_url(href or "")))
        finally:
            browser.close()
    return snippets


def _as_documents(items: list[Union[str, WebSnippet]]) -> list[WebSnippet]:
    """Normalize provider output (str or WebSnippet) to WebSnippet."""

    return [it if isinstance(it, WebSnippet) else WebSnippet(text=str(it)) for it in items]


def get_web_documents(
    query: str, *, num: int = 6, settings: Optional[Settings] = None
) -> list[WebSnippet]:
    """Return web results (text + source URL) via the first healthy provider.

    Order: Serper -> DuckDuckGo -> Playwright. Providers that raise are tripped
    into a cooldown so they are skipped on subsequent calls. Returns ``[]`` when
    all providers fail; check :func:`last_status` to distinguish that case.
    """

    settings = settings or get_settings()
    cooldown = settings.provider_cooldown_seconds

    providers: list[tuple[str, bool, Callable[[str, int, Settings], list]]] = [
        ("serper", True, _serper_search),
        ("duckduckgo", settings.duckduckgo_fallback_enabled, _duckduckgo_search),
    ]
    if settings.playwright_fallback_enabled and _playwright_available():
        providers.append(("playwright", True, _playwright_search))

    for name, enabled, fn in providers:
        if not enabled or not _HEALTH[name].available():
            continue
        try:
            result = fn(query, num, settings)
        except Exception as exc:  # noqa: BLE001 - any provider failure trips its breaker
            _HEALTH[name].trip(cooldown)
            _log.warning("web_knowledge: provider %s failed (%s); cooling down", name, exc)
            continue
        if result:
            docs = _as_documents(result)
            _STATUS.provider = name
            _STATUS.all_failed = False
            _log.debug("web_knowledge: %s served %d snippets for %r", name, len(docs), query)
            return docs

    _STATUS.provider = None
    _STATUS.all_failed = True
    _log.warning("web_knowledge: all providers failed for %r", query)
    return []


def get_web_snippets(query: str, *, num: int = 6, settings: Optional[Settings] = None) -> list[str]:
    """Text-only view of :func:`get_web_documents` (backward-compatible)."""

    return [d.text for d in get_web_documents(query, num=num, settings=settings)]
