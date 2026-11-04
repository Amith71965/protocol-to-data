"""Runtime configuration.

Loads from the environment and an optional ``.env``. Importing this module and
constructing :class:`Settings` must succeed with **no** secrets present — the
pipeline only needs a key for the live Phase 4 extraction, and everything else
(including the whole test suite) runs from cached responses.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["anthropic", "openrouter"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    llm_provider: Provider = Field(default="anthropic", validation_alias="P2D_LLM_PROVIDER")
    llm_model: str = Field(default="claude-opus-5", validation_alias="P2D_LLM_MODEL")

    #: When true the extractor reads cached responses only and never touches the network.
    llm_cache_only: bool = Field(default=True, validation_alias="P2D_LLM_CACHE_ONLY")

    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str | None = Field(default=None, validation_alias="ANTHROPIC_BASE_URL")
    openrouter_api_key: SecretStr | None = Field(
        default=None, validation_alias="OPENROUTER_API_KEY"
    )

    def api_key_for(self, provider: Provider | None = None) -> SecretStr | None:
        """Return the configured key for ``provider``, or None if it is absent."""
        match provider or self.llm_provider:
            case "anthropic":
                return self.anthropic_api_key
            case "openrouter":
                return self.openrouter_api_key

    def has_live_credentials(self) -> bool:
        """True when a live call could be attempted for the selected provider."""
        key = self.api_key_for()
        return key is not None and bool(key.get_secret_value().strip())


def load_settings() -> Settings:
    """Build settings from the current environment."""
    return Settings()
