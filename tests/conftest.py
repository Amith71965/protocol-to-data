"""Shared fixtures.

The suite must be hermetic: it never reads the developer's ambient configuration
and never makes a network call.
"""

from __future__ import annotations

import pytest

#: Environment variables that would otherwise leak the developer's own setup
#: into a test run.
_LEAKY_VARS = (
    "P2D_LLM_PROVIDER",
    "P2D_LLM_MODEL",
    "P2D_LLM_CACHE_ONLY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "OPENROUTER_API_KEY",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Remove provider configuration and run from a directory with no ``.env``."""
    for name in _LEAKY_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return monkeypatch
