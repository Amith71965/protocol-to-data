"""Swappable model providers.

The extraction depends on this interface, not on a vendor SDK, so the provider
can be changed without touching the extraction logic. Each adapter is
responsible for one thing: turning a prompt plus a JSON schema into a JSON
string.
"""

from __future__ import annotations

import json
import os
from typing import Protocol, runtime_checkable

from p2d.criteria.cache import CacheMissError, ResponseCache, request_key
from p2d.settings import Settings


@runtime_checkable
class LLMProvider(Protocol):
    """Anything that can answer a schema-constrained prompt."""

    name: str
    model: str

    def complete(self, system: str, prompt: str, schema: dict) -> str:
        """Return the model's JSON response as text."""
        ...


class AnthropicProvider:
    """Claude, through the Anthropic SDK."""

    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        self.name = "anthropic"
        self.model = model
        self._api_key = api_key
        self._base_url = base_url

    def complete(self, system: str, prompt: str, schema: dict) -> str:
        import anthropic

        client = anthropic.Anthropic(
            api_key=self._api_key, **({"base_url": self._base_url} if self._base_url else {})
        )
        # A tool with the target schema is how the model is held to the shape;
        # asking for JSON in prose is not enforceable.
        response = client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system,
            tools=[
                {
                    "name": "record_criteria",
                    "description": "Record the extracted eligibility criteria.",
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": "record_criteria"},
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if block.type == "tool_use":
                return json.dumps(block.input)
        raise RuntimeError("Model returned no structured output.")


class OpenRouterProvider:
    """Any model reachable through OpenRouter's OpenAI-compatible API."""

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, model: str, api_key: str):
        self.name = "openrouter"
        self.model = model
        self._api_key = api_key

    def complete(self, system: str, prompt: str, schema: dict) -> str:
        import httpx

        response = httpx.post(
            self.BASE_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "criteria", "strict": True, "schema": schema},
                },
            },
            timeout=180.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class CachingProvider:
    """Wraps a provider so an answer is fetched at most once.

    In ``cache_only`` mode a miss raises instead of reaching the network, which
    is how the test suite and CI are kept offline.
    """

    def __init__(self, inner: LLMProvider, cache: ResponseCache, *, cache_only: bool = False):
        self._inner = inner
        self._cache = cache
        self._cache_only = cache_only
        self.name = inner.name
        self.model = inner.model

    def complete(self, system: str, prompt: str, schema: dict) -> str:
        key = request_key(self.name, self.model, system, prompt, schema)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        if self._cache_only:
            raise CacheMissError(
                f"No cached response for {key[:12]}. Run the extraction with a "
                "configured API key to populate the cache."
            )
        response = self._inner.complete(system, prompt, schema)
        self._cache.put(key, response, provider=self.name, model=self.model)
        return response


class StubProvider:
    """Returns a canned response. For tests only."""

    def __init__(self, response: str, model: str = "stub"):
        self.name = "stub"
        self.model = model
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, prompt: str, schema: dict) -> str:  # noqa: ARG002
        self.calls.append((system, prompt))
        return self.response


class MissingCredentialsError(RuntimeError):
    """No API key is configured for the selected provider."""


def build_provider(settings: Settings, cache: ResponseCache) -> CachingProvider:
    """Construct the configured provider, wrapped in the cache."""
    key = settings.api_key_for()
    if settings.llm_cache_only:
        # Nothing will be called, so a placeholder inner provider is enough.
        inner: LLMProvider = StubProvider("", model=settings.llm_model)
    elif key is None or not key.get_secret_value().strip():
        raise MissingCredentialsError(
            f"No API key for provider '{settings.llm_provider}'. "
            "Add one to .env (see .env.example) or set P2D_LLM_CACHE_ONLY=true."
        )
    elif settings.llm_provider == "anthropic":
        inner = AnthropicProvider(
            settings.llm_model,
            key.get_secret_value(),
            settings.anthropic_base_url or os.environ.get("ANTHROPIC_BASE_URL"),
        )
    else:
        inner = OpenRouterProvider(settings.llm_model, key.get_secret_value())

    return CachingProvider(inner, cache, cache_only=settings.llm_cache_only)
