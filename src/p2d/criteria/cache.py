"""On-disk cache of model responses.

Every request is keyed by a hash of everything that determines the answer: the
provider, the model, the prompts and the schema. A cached entry therefore
belongs to exactly one request, and changing the prompt cannot silently reuse
an answer to a different question.

The cache exists so the test suite and CI never make a network call, and so a
reported metric can be reproduced from committed inputs rather than re-run
against a model that may since have changed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


def request_key(provider: str, model: str, system: str, prompt: str, schema: dict) -> str:
    """Stable identifier for one request."""
    payload = json.dumps(
        {
            "provider": provider,
            "model": model,
            "system": system,
            "prompt": prompt,
            "schema": schema,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class CacheMissError(KeyError):
    """A response is not cached and the cache is in read-only mode."""


@dataclass
class ResponseCache:
    directory: Path

    def path_for(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> str | None:
        path = self.path_for(key)
        if not path.exists():
            return None
        return json.loads(path.read_text())["response"]

    def put(self, key: str, response: str, *, provider: str, model: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path_for(key).write_text(
            json.dumps(
                {
                    "key": key,
                    "provider": provider,
                    "model": model,
                    "cached_at": datetime.now(UTC).isoformat(),
                    "response": response,
                },
                indent=2,
            )
        )

    def __contains__(self, key: str) -> bool:
        return self.path_for(key).exists()

    def __len__(self) -> int:
        return len(list(self.directory.glob("*.json"))) if self.directory.exists() else 0
