"""Tests for the P2 provenance lints (gap-05 §3.5 + §6).

Exercises:

- Registry contains both lints (auto-registered via
  :func:`lethe.audit.lints.register_p2_lints` at integrity import).
- ``provenance-required`` flags empty/null ``source_uri``; clean on
  fully-provenanced episodes.
- ``provenance-resolvable`` resolves ``s4a:`` / ``s4b:`` to real files
  under the tenant's S4 layout; flags missing artifacts.
- ``provenance-resolvable`` accepts non-S4 URIs only when the tenant
  has a ``provenance_drop_count`` row in ``tenant_config`` (dev sub-
  plan §8 Q5).
- Tenant isolation: a violation under tenant A is not surfaced under
  tenant B (each lint invocation is scoped to one tenant).
- CLI smoke (``lethe-audit lint --integrity``) on an empty tenant still
  exits clean with the lints registered.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from lethe.audit.integrity import REGISTRY, lint_integrity
from lethe.audit.lints import (
    check_provenance_required,
    check_provenance_resolvable,
)
from lethe.runtime.provenance import PROVENANCE_DROPPED_COUNT_KEY
from lethe.store.s1_graph.client import _InMemoryGraphBackend
from lethe.store.s2_meta.schema import S2Schema
from lethe.store.s4_md import S4Layout

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def s2_conn(tenant_root: Path) -> Iterator[sqlite3.Connection]:
    """Open an S2 connection rooted at the test tenant_root."""
    tenant_root.mkdir(parents=True, exist_ok=True)
    conn = S2Schema(tenant_root=tenant_root).create()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def s4(tenant_root: Path) -> S4Layout:
    """Create the S4 layout for the test tenant."""
    tenant_root.mkdir(parents=True, exist_ok=True)
    layout = S4Layout(tenant_root=tenant_root)
    layout.create()
    return layout


@pytest.fixture
def graph() -> _InMemoryGraphBackend:
    """Fresh in-memory graph backend for each test."""
    return _InMemoryGraphBackend()


def _seed_episode(
    backend: _InMemoryGraphBackend,
    *,
    tenant_id: str,
    episode_id: str,
    source_uri: str,
) -> None:
    """Seed one episode into the in-memory backend under ``tenant_id``."""
    if tenant_id not in backend._tenants:  # noqa: SLF001 - test fixture
        backend.bootstrap_tenant(tenant_id)
    backend.add_episode(
        group_id=tenant_id,
        episode_id=episode_id,
        body="body-stub",
        source_uri=source_uri,
        ts_recorded="2024-01-01T00:00:00Z",
        intent="remember:fact",
    )


# ---------------------------------------------------------------------------
# Registry presence
# ---------------------------------------------------------------------------


def test_registry_includes_both_provenance_lints() -> None:
    names = REGISTRY.names()
    assert "provenance-required" in names
    assert "provenance-resolvable" in names


def test_cli_smoke_still_clean_on_empty_tenant(lethe_home: Path) -> None:
    """The two registered lints must not invent findings on a fresh tenant."""
    result = lint_integrity(tenant_id="smoke-tenant", storage_root=lethe_home)
    assert result.status == "clean"
    assert result.findings == ()


# ---------------------------------------------------------------------------
# provenance-required
# ---------------------------------------------------------------------------


def test_provenance_required_clean_when_every_episode_has_source_uri(
    graph: _InMemoryGraphBackend,
) -> None:
    _seed_episode(
        graph, tenant_id="t1", episode_id="ep1", source_uri="s4a:doc.md"
    )
    _seed_episode(
        graph, tenant_id="t1", episode_id="ep2", source_uri="external:rfc-1234"
    )
    findings = check_provenance_required(
        tenant_id="t1", episodes=graph._episodes_for("t1")
    )
    assert findings == []


def test_provenance_required_flags_empty_source_uri(
    graph: _InMemoryGraphBackend,
) -> None:
    _seed_episode(
        graph, tenant_id="t1", episode_id="ep1", source_uri="s4a:doc.md"
    )
    # Simulate an out-of-band write with empty source_uri (the runtime
    # API would have refused; the lint exists to catch this case).
    graph.bootstrap_tenant("t1")  # idempotent
    graph._episodes["t1"].append(  # noqa: SLF001 - injecting a bad row.
        {
            "episode_id": "bad-ep",
            "body": "x",
            "source_uri": "",
            "ts_recorded": "2024-01-01T00:00:00Z",
            "intent": "remember:fact",
        }
    )
    findings = check_provenance_required(
        tenant_id="t1", episodes=graph._episodes_for("t1")
    )
    assert len(findings) == 1
    assert "bad-ep" in findings[0]
    assert "t1" in findings[0]


def test_provenance_required_tenant_isolation(
    graph: _InMemoryGraphBackend,
) -> None:
    """A bad episode under tenant A must not surface in tenant B's findings."""
    graph.bootstrap_tenant("ta")
    graph.bootstrap_tenant("tb")
    graph._episodes["ta"].append(  # noqa: SLF001 - injecting a bad row.
        {
            "episode_id": "bad-a",
            "body": "x",
            "source_uri": "",
            "ts_recorded": "2024-01-01T00:00:00Z",
            "intent": "remember:fact",
        }
    )
    _seed_episode(
        graph, tenant_id="tb", episode_id="ep-b", source_uri="s4a:fine.md"
    )

    findings_a = check_provenance_required(
        tenant_id="ta", episodes=graph._episodes_for("ta")
    )
    findings_b = check_provenance_required(
        tenant_id="tb", episodes=graph._episodes_for("tb")
    )
    assert len(findings_a) == 1
    assert findings_b == []


# ---------------------------------------------------------------------------
# provenance-resolvable
# ---------------------------------------------------------------------------


def test_provenance_resolvable_clean_when_s4a_artifact_exists(
    tenant_root: Path,
    graph: _InMemoryGraphBackend,
    s2_conn: sqlite3.Connection,
    s4: S4Layout,
) -> None:
    (s4.s4a_dir / "doc.md").write_text("# real artifact\n")
    _seed_episode(
        graph, tenant_id="t1", episode_id="ep1", source_uri="s4a:doc.md"
    )
    findings = check_provenance_resolvable(
        tenant_id="t1",
        episodes=graph._episodes_for("t1"),
        tenant_root=tenant_root,
        s2_conn=s2_conn,
    )
    assert findings == []


def test_provenance_resolvable_clean_when_s4b_artifact_exists(
    tenant_root: Path,
    graph: _InMemoryGraphBackend,
    s2_conn: sqlite3.Connection,
    s4: S4Layout,
) -> None:
    (s4.s4b_dir / "projection.json").write_text("{}")
    _seed_episode(
        graph,
        tenant_id="t1",
        episode_id="ep1",
        source_uri="s4b:projection.json",
    )
    findings = check_provenance_resolvable(
        tenant_id="t1",
        episodes=graph._episodes_for("t1"),
        tenant_root=tenant_root,
        s2_conn=s2_conn,
    )
    assert findings == []


def test_provenance_resolvable_flags_missing_s4a_artifact(
    tenant_root: Path,
    graph: _InMemoryGraphBackend,
    s2_conn: sqlite3.Connection,
    s4: S4Layout,  # noqa: ARG001 - ensures s4a/ dir exists but file absent.
) -> None:
    _seed_episode(
        graph, tenant_id="t1", episode_id="ep1", source_uri="s4a:missing.md"
    )
    findings = check_provenance_resolvable(
        tenant_id="t1",
        episodes=graph._episodes_for("t1"),
        tenant_root=tenant_root,
        s2_conn=s2_conn,
    )
    assert len(findings) == 1
    assert "ep1" in findings[0]
    assert "missing.md" in findings[0]


def test_provenance_resolvable_flags_non_s4_without_drop_policy(
    tenant_root: Path,
    graph: _InMemoryGraphBackend,
    s2_conn: sqlite3.Connection,
    s4: S4Layout,  # noqa: ARG001
) -> None:
    _seed_episode(
        graph, tenant_id="t1", episode_id="ep1", source_uri="external:rfc-1234"
    )
    findings = check_provenance_resolvable(
        tenant_id="t1",
        episodes=graph._episodes_for("t1"),
        tenant_root=tenant_root,
        s2_conn=s2_conn,
    )
    assert len(findings) == 1
    assert "ep1" in findings[0]
    assert PROVENANCE_DROPPED_COUNT_KEY in findings[0]


def test_provenance_resolvable_accepts_non_s4_when_drop_policy_row_present(
    tenant_root: Path,
    graph: _InMemoryGraphBackend,
    s2_conn: sqlite3.Connection,
    s4: S4Layout,  # noqa: ARG001
) -> None:
    """Per sub-plan §8 Q5, a ``provenance_drop_count`` row is the opt-in."""
    s2_conn.execute(
        "INSERT INTO tenant_config (key, value) VALUES (?, ?)",
        (PROVENANCE_DROPPED_COUNT_KEY, "0"),
    )
    _seed_episode(
        graph, tenant_id="t1", episode_id="ep1", source_uri="external:rfc-1234"
    )
    _seed_episode(
        graph,
        tenant_id="t1",
        episode_id="ep2",
        source_uri="self_observation:agent-a",
    )
    findings = check_provenance_resolvable(
        tenant_id="t1",
        episodes=graph._episodes_for("t1"),
        tenant_root=tenant_root,
        s2_conn=s2_conn,
    )
    assert findings == []


def test_provenance_resolvable_drop_policy_does_not_excuse_missing_s4_artifact(
    tenant_root: Path,
    graph: _InMemoryGraphBackend,
    s2_conn: sqlite3.Connection,
    s4: S4Layout,  # noqa: ARG001
) -> None:
    """The drop-policy row only excuses non-S4 schemes; S4 misses still fail."""
    s2_conn.execute(
        "INSERT INTO tenant_config (key, value) VALUES (?, ?)",
        (PROVENANCE_DROPPED_COUNT_KEY, "0"),
    )
    _seed_episode(
        graph, tenant_id="t1", episode_id="ep1", source_uri="s4a:missing.md"
    )
    findings = check_provenance_resolvable(
        tenant_id="t1",
        episodes=graph._episodes_for("t1"),
        tenant_root=tenant_root,
        s2_conn=s2_conn,
    )
    assert len(findings) == 1
    assert "missing.md" in findings[0]


def test_provenance_resolvable_ignores_empty_source_uri(
    tenant_root: Path,
    graph: _InMemoryGraphBackend,
    s2_conn: sqlite3.Connection,
    s4: S4Layout,  # noqa: ARG001
) -> None:
    """Empty URIs are the provenance-required lint's job, not this one's."""
    graph.bootstrap_tenant("t1")
    graph._episodes["t1"].append(  # noqa: SLF001
        {
            "episode_id": "bad-ep",
            "body": "x",
            "source_uri": "",
            "ts_recorded": "2024-01-01T00:00:00Z",
            "intent": "remember:fact",
        }
    )
    findings = check_provenance_resolvable(
        tenant_id="t1",
        episodes=graph._episodes_for("t1"),
        tenant_root=tenant_root,
        s2_conn=s2_conn,
    )
    assert findings == []


def test_provenance_resolvable_empty_s4_relpath_is_a_finding(
    tenant_root: Path,
    graph: _InMemoryGraphBackend,
    s2_conn: sqlite3.Connection,
    s4: S4Layout,  # noqa: ARG001
) -> None:
    """A bare ``s4a:`` (no path after the scheme) is unresolvable."""
    _seed_episode(graph, tenant_id="t1", episode_id="ep1", source_uri="s4a:")
    findings = check_provenance_resolvable(
        tenant_id="t1",
        episodes=graph._episodes_for("t1"),
        tenant_root=tenant_root,
        s2_conn=s2_conn,
    )
    assert len(findings) == 1
    assert "ep1" in findings[0]
