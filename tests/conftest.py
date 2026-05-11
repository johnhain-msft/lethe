"""Global pytest fixtures for the Lethe test suite.

Enforces the ``LETHE_HOME`` isolation rule from the facilitator handoff:
tests must NEVER touch the real ``~/.lethe`` directory.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def lethe_home(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Provide an isolated ``LETHE_HOME`` for the duration of one test."""
    home = tmp_path_factory.mktemp("lethe-home")
    real_home = Path.home() / ".lethe"
    assert home.resolve() != real_home.resolve(), (
        "LETHE_HOME fixture would shadow the real ~/.lethe; refusing"
    )
    monkeypatch.setenv("LETHE_HOME", str(home))
    yield home


@pytest.fixture
def tenant_root(lethe_home: Path) -> Path:
    """Per-tenant root under the test ``LETHE_HOME`` (``smoke-tenant`` by default)."""
    return lethe_home / "tenants" / "smoke-tenant"
