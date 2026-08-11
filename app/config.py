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

    # --- Google Gemini (single free API key powers both tiers) ---
    gemini_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GEMINI_API_KEY", "gemini_api_key", "GOOGLE_API_KEY", "google_api_key"
        ),
    )
    # Narrative / explain node — quality tier.
    gemini_full_model: str = Field(
        default="gemini-flash-latest",
        validation_alias=AliasChoices("GEMINI_FULL_MODEL", "gemini_full_model"),
    )
    # Intake / clarify / extraction — cheap, high-volume tier (fans out per airline).
    gemini_mini_model: str = Field(
        default="gemini-flash-lite-latest",
        validation_alias=AliasChoices("GEMINI_MINI_MODEL", "gemini_mini_model"),
    )

    # --- Gemini free-tier rate-limit protection ---
    # A shared client-side limiter throttles ALL Gemini calls (including the
    # concurrent per-airline enrichment fan-out) to stay under the free-tier
    # requests-per-minute cap, avoiding 429s before they happen.
    gemini_requests_per_minute: float = Field(
        default=10.0,
        validation_alias=AliasChoices("GEMINI_REQUESTS_PER_MINUTE", "gemini_requests_per_minute"),
        description="Client-side throughput cap shared across all Gemini calls (free tier ~10-15 RPM).",
    )
    # On a 429 the client retries with exponential backoff before falling back.
    gemini_max_retries: int = Field(
        default=5,
        validation_alias=AliasChoices("GEMINI_MAX_RETRIES", "gemini_max_retries"),
        description="Retries with exponential backoff on transient 429/5xx before giving up.",
    )
    gemini_timeout: float = Field(
        default=45.0,
        validation_alias=AliasChoices("GEMINI_TIMEOUT", "gemini_timeout"),
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
    # Interactive docs (/docs, /redoc, /openapi.json) are OFF unless explicitly
    # enabled — keep them off in the public deployment, on for local dev.
    enable_docs: bool = Field(
        default=False,
        validation_alias=AliasChoices("ENABLE_DOCS", "enable_docs"),
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
    # Hard daily ceiling on LIVE SerpAPI searches (cache hits don't count), so no
    # amount of traffic can blow the 250/month free cap. 0 = unlimited (local dev).
    serpapi_daily_budget: int = Field(
        default=0,
        validation_alias=AliasChoices("SERPAPI_DAILY_BUDGET", "serpapi_daily_budget"),
        description="Max live SerpAPI searches per day (0 = unlimited).",
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
    enrich_min_corroboration: int = Field(
        default=2,
        validation_alias=AliasChoices("ENRICH_MIN_CORROBORATION", "enrich_min_corroboration"),
        description="Min distinct web snippets that must support a discount (unless an official source vouches for it).",
    )
    enrich_min_confidence: float = Field(
        default=0.6,
        validation_alias=AliasChoices("ENRICH_MIN_CONFIDENCE", "enrich_min_confidence"),
        description="Min LLM confidence (0-1) required before a discount is folded into the price.",
    )
    enrich_trust_official_single: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENRICH_TRUST_OFFICIAL_SINGLE", "enrich_trust_official_single"),
        description="Accept a discount backed by the airline's own official domain even with a single source.",
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
