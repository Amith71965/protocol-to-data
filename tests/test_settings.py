"""Configuration loads with no secrets present."""

from __future__ import annotations

import pydantic
import pytest

from p2d.settings import Settings, load_settings


def test_loads_without_any_secrets(clean_env) -> None:
    settings = load_settings()

    assert settings.llm_provider == "anthropic"
    assert settings.llm_model
    assert settings.anthropic_api_key is None
    assert settings.openrouter_api_key is None


def test_cache_only_defaults_on(clean_env) -> None:
    """The safe default is to never reach the network."""
    assert load_settings().llm_cache_only is True


def test_has_live_credentials_false_without_key(clean_env) -> None:
    assert load_settings().has_live_credentials() is False


def test_has_live_credentials_true_with_key(clean_env) -> None:
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    assert load_settings().has_live_credentials() is True


def test_blank_key_is_not_live_credentials(clean_env) -> None:
    clean_env.setenv("ANTHROPIC_API_KEY", "   ")
    assert load_settings().has_live_credentials() is False


def test_api_key_is_not_exposed_in_repr(clean_env) -> None:
    """A key must never leak through logs or tracebacks."""
    secret = "sk-ant-should-not-appear"
    clean_env.setenv("ANTHROPIC_API_KEY", secret)

    settings = load_settings()

    assert secret not in repr(settings)
    assert secret not in str(settings)
    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == secret


def test_provider_selects_matching_key(clean_env) -> None:
    clean_env.setenv("P2D_LLM_PROVIDER", "openrouter")
    clean_env.setenv("OPENROUTER_API_KEY", "or-test-key")

    settings = load_settings()

    assert settings.llm_provider == "openrouter"
    assert settings.has_live_credentials() is True
    assert settings.api_key_for("anthropic") is None


def test_settings_rejects_unknown_provider(clean_env) -> None:
    clean_env.setenv("P2D_LLM_PROVIDER", "not-a-provider")

    with pytest.raises(pydantic.ValidationError):
        Settings()
