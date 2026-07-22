"""Application configuration loaded from environment / .env.

All secrets live in ``.env`` (git-ignored). Field names map to the environment
variables via ``AliasChoices`` so we tolerate the exact casing already present
in the user's ``.env`` (e.g. ``SerpApi_key``).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed access to all runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Web search (enrichment) ---
    serper_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("SERPER_API_KEY", "serper_api_key"),
    )

    # --- Flight offers (primary data source) ---
    serpapi_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("SERPAPI_API_KEY", "SerpApi_key", "serpapi_key"),
    )

    # --- Azure OpenAI: GPT-5 (narrative / explain) ---
    azure_gpt5_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices("AZURE_GPT5_ENDPOINT", "azure_gpt5_endpoint"),
    )
    azure_gpt5_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("AZURE_GPT5_API_KEY", "azure_gpt5_api_key"),
    )
    azure_gpt5_api_version: str = Field(
        default="2024-12-01-preview",
        validation_alias=AliasChoices("AZURE_GPT5_API_VERSION", "azure_gpt5_api_version"),
    )
    azure_gpt5_deployment: str = Field(
        default="gpt-5",
        validation_alias=AliasChoices("AZURE_GPT5_DEPLOYMENT", "azure_gpt5_deployment"),
    )

    # --- Azure OpenAI: GPT-5-mini (intake / clarify / extraction) ---
    azure_gpt5_mini_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices("AZURE_GPT5_MINI_ENDPOINT", "azure_gpt5_mini_endpoint"),
    )
    azure_gpt5_mini_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("AZURE_GPT5_MINI_API_KEY", "azure_gpt5_mini_api_key"),
    )
    azure_gpt5_mini_api_version: str = Field(
        default="2024-12-01-preview",
        validation_alias=AliasChoices(
            "AZURE_GPT5_MINI_API_VERSION", "azure_gpt5_mini_api_version"
        ),
    )
    azure_gpt5_mini_deployment: str = Field(
        default="gpt-5-mini",
        validation_alias=AliasChoices("AZURE_GPT5_MINI_DEPLOYMENT", "azure_gpt5_mini_deployment"),
    )

    # --- Request defaults ---
    default_currency: str = "USD"
    serpapi_base_url: str = "https://serpapi.com/search"
    serper_base_url: str = "https://google.serper.dev/search"

    # --- API / CORS ---
    cors_allow_origins: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("CORS_ALLOW_ORIGINS", "cors_allow_origins"),
        description="Comma-separated list of allowed frontend origins.",
    )

    # --- SerpAPI response cache (protects the 250 searches/month free cap) ---
    serpapi_cache_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("SERPAPI_CACHE_ENABLED", "serpapi_cache_enabled"),
    )
    serpapi_cache_dir: str = Field(
        default=".cache/serpapi",
        validation_alias=AliasChoices("SERPAPI_CACHE_DIR", "serpapi_cache_dir"),
    )
    serpapi_cache_ttl_seconds: int = Field(
        default=21600,  # 6 hours
        validation_alias=AliasChoices("SERPAPI_CACHE_TTL_SECONDS", "serpapi_cache_ttl_seconds"),
    )

    # --- Downloadable per-search reports ---
    reports_dir: str = Field(
        default="reports",
        validation_alias=AliasChoices("REPORTS_DIR", "reports_dir"),
        description="Directory (repo-root relative or absolute) where generated reports are saved.",
    )

    # --- Enrichment knowledge cache (baggage fees, discounts, allowances) ---
    kb_cache_dir: str = Field(
        default=".cache/kb",
        validation_alias=AliasChoices("KB_CACHE_DIR", "kb_cache_dir"),
    )
    kb_cache_ttl_seconds: int = Field(
        default=1209600,  # 14 days — fees/programs change slowly
        validation_alias=AliasChoices("KB_CACHE_TTL_SECONDS", "kb_cache_ttl_seconds"),
    )
    enrich_max_workers: int = Field(
        default=6,
        validation_alias=AliasChoices("ENRICH_MAX_WORKERS", "enrich_max_workers"),
        description="Max concurrent per-airline enrichment lookups.",
    )
    enrich_timeout: float = Field(
        default=45.0,
        validation_alias=AliasChoices("ENRICH_TIMEOUT", "enrich_timeout"),
        description="Overall budget (s) for concurrent enrichment; slow airlines are skipped.",
    )

    # --- Web-knowledge fallback providers ---
    duckduckgo_fallback_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("DUCKDUCKGO_FALLBACK_ENABLED", "duckduckgo_fallback_enabled"),
    )
    playwright_fallback_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("PLAYWRIGHT_FALLBACK_ENABLED", "playwright_fallback_enabled"),
    )
    web_search_timeout: float = Field(
        default=20.0,
        validation_alias=AliasChoices("WEB_SEARCH_TIMEOUT", "web_search_timeout"),
    )
    provider_cooldown_seconds: int = Field(
        default=600,  # circuit-breaker: skip a failing provider for 10 min
        validation_alias=AliasChoices("PROVIDER_COOLDOWN_SECONDS", "provider_cooldown_seconds"),
    )

    # --- Currency conversion (keyless FX for unsupported Google Flights currencies) ---
    fx_api_base: str = Field(
        default="https://open.er-api.com/v6/latest",
        validation_alias=AliasChoices("FX_API_BASE", "fx_api_base"),
    )
    fx_cache_dir: str = Field(
        default=".cache/fx",
        validation_alias=AliasChoices("FX_CACHE_DIR", "fx_cache_dir"),
    )
    fx_cache_ttl_seconds: int = Field(
        default=21600,  # 6 hours — intraday FX drift is immaterial for fare display
        validation_alias=AliasChoices("FX_CACHE_TTL_SECONDS", "fx_cache_ttl_seconds"),
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""

    return Settings()
