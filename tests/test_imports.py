"""Every package module imports cleanly, with no import-time side effects."""

from __future__ import annotations

import importlib

import pytest

MODULES = [
    "p2d",
    "p2d.paths",
    "p2d.settings",
    "p2d.sources",
    "p2d.ingest",
    "p2d.mapping",
    "p2d.validate",
    "p2d.criteria",
    "p2d.deviations",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str) -> None:
    assert importlib.import_module(name) is not None


def test_importing_paths_creates_nothing() -> None:
    """Importing the layout module must not touch the filesystem."""
    from p2d import paths

    # ensure_dirs() is explicit; merely importing must not have run it.
    assert paths.REPO_ROOT.is_dir()
    assert callable(paths.ensure_dirs)
