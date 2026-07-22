"""Factories for the two Azure OpenAI deployments.

- ``get_mini_llm``  -> GPT-5-mini : intake parsing, clarify, extraction (cheap).
- ``get_full_llm``  -> GPT-5      : narrative / explain node (quality).

Both are cached so we reuse a single client per process.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import AzureChatOpenAI

from app.config import get_settings


@lru_cache(maxsize=1)
def get_mini_llm() -> AzureChatOpenAI:
    s = get_settings()
    return AzureChatOpenAI(
        azure_endpoint=s.azure_gpt5_mini_endpoint,
        api_key=s.azure_gpt5_mini_api_key,
        api_version=s.azure_gpt5_mini_api_version,
        azure_deployment=s.azure_gpt5_mini_deployment,
        temperature=1,
        timeout=45,
        max_retries=1,
    )


@lru_cache(maxsize=1)
def get_full_llm() -> AzureChatOpenAI:
    s = get_settings()
    return AzureChatOpenAI(
        azure_endpoint=s.azure_gpt5_endpoint,
        api_key=s.azure_gpt5_api_key,
        api_version=s.azure_gpt5_api_version,
        azure_deployment=s.azure_gpt5_deployment,
        temperature=1,
        # Explanations have a rule-based fallback, so fail over fast rather than
        # stalling a whole search when the GPT-5 endpoint is slow.
        timeout=30,
        max_retries=1,
    )
