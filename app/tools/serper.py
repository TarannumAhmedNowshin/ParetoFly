"""Serper.dev web-search client (enrichment).

Used to look up facts SerpAPI's flight payload does not reliably provide, such
as an airline's checked-baggage fee. Returns plain snippet strings for an LLM
to read.
"""

from __future__ import annotations

from typing import Optional

import httpx

from app.config import Settings, get_settings


class SerperError(RuntimeError):
    """Raised when the Serper request fails."""


def web_search(
    query: str,
    *,
    num: int = 5,
    settings: Optional[Settings] = None,
    client: Optional[httpx.Client] = None,
    timeout: float = 20.0,
) -> list[str]:
    """Run a Serper web search and return ``title - snippet`` strings."""

    settings = settings or get_settings()
    if not settings.serper_api_key:
        raise SerperError("SERPER_API_KEY is not configured in .env")

    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        response = client.post(
            settings.serper_base_url,
            headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num},
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise SerperError(f"Serper request failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    snippets: list[str] = []
    answer_box = payload.get("answerBox") or {}
    if answer_box.get("answer"):
        snippets.append(str(answer_box["answer"]))
    if answer_box.get("snippet"):
        snippets.append(str(answer_box["snippet"]))
    for item in payload.get("organic", [])[:num]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        if snippet:
            snippets.append(f"{title} - {snippet}")
    return snippets


def web_search_documents(
    query: str,
    *,
    num: int = 5,
    settings: Optional[Settings] = None,
    client: Optional[httpx.Client] = None,
    timeout: float = 20.0,
) -> list[tuple[str, str]]:
    """Like :func:`web_search` but also return each result's source URL.

    Returns ``(text, url)`` pairs. The answer box has no URL, so its ``url`` is
    an empty string. Callers that only need text can keep using
    :func:`web_search`.
    """

    settings = settings or get_settings()
    if not settings.serper_api_key:
        raise SerperError("SERPER_API_KEY is not configured in .env")

    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        response = client.post(
            settings.serper_base_url,
            headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num},
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise SerperError(f"Serper request failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    docs: list[tuple[str, str]] = []
    answer_box = payload.get("answerBox") or {}
    if answer_box.get("answer"):
        docs.append((str(answer_box["answer"]), str(answer_box.get("link", ""))))
    if answer_box.get("snippet"):
        docs.append((str(answer_box["snippet"]), str(answer_box.get("link", ""))))
    for item in payload.get("organic", [])[:num]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        if snippet:
            docs.append((f"{title} - {snippet}", str(item.get("link", ""))))
    return docs
