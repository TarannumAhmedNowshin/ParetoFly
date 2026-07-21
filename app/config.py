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

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""

    return Settings()
