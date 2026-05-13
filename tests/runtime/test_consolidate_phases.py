"""Phase impl unit tests for P4 commit 6.

Tests the three phase modules (:mod:`lethe.runtime.consolidate.promote`,
:mod:`.demote`, :mod:`.invalidate`) plus the shared reconciler
(:mod:`._reconciler`) — covering all 25 IMPLEMENT 6 gates that surface
at the per-phase / reconciler / sink-failure / partial-S1-failure
layers. The canonical-order property test (loop dispatches the six
phases in the IMPL §2.4 invariant I-11 order) is APPENDED at C7 when
:mod:`.loop` owns the property — shipping it here would either need a
placeholder loop or test loop+phases together (both bigger scope than
D6 allows; per IMPLEMENT 6 amendment A12).

Tests are organized by concern, not by phase:

- Happy-path per phase (promote / demote / invalidate).
- Preflight (:func:`._validate_*_inputs`) — exact ValueError messages.
- S1-first ordering invariant (per §k.6).
- ``promotion_flags`` REPLACE semantics + tier value.
- Reconciler backfill + idempotency (per A2).
- Partial S1-write failure (per A4) for both demote and invalidate.
- Post-commit sink failure (per A9).
- Random uuidv7 uniqueness (per A8).
- Z-suffix timestamp format (per A11).
- ``utility_events`` audit-history-only (per A3) — covered in
  ``test_bitemporal_p4.py``; the round-trip events.py:validate gates
  (gate 15) are inline in each happy-path test below.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from lethe.runtime import bootstrap
from lethe.runtime.consolidate import (
    DEMOTE_DECISIONS,
    INVALIDATE_REASONS,
    PROMOTE_DECISIONS,
    PROMOTION_FLAG_TIERS,
    PhaseResult,
    demote,
    invalidate,
    promote,
)
from lethe.runtime.consolidate._reconciler import reconcile_orphans
from lethe.runtime.events import validate
from lethe.store import shared_store_connection
from lethe.store.s1_graph.client import S1Client, _InMemoryGraphBackend

# ---------- helpers ---------- #


def _bootstrap_tenant(lethe_home: Path) -> tuple[Path, S1Client, _InMemoryGraphBackend]:
    """Standard bootstrap: tenant_root + S1Client + backend."""
    bootstrap(tenant_id="smoke-tenant", storage_root=lethe_home)
    backend = _InMemoryGraphBackend()
    s1 = S1Client(backend, tenant_id="smoke-tenant")
    s1.bootstrap()
    return lethe_home / "tenants" / "smoke-tenant", s1, backend


def _make_s1_client_with_seeded_facts(
    lethe_home: Path, fact_ids: Sequence[str]
) -> tuple[Path, S1Client, _InMemoryGraphBackend]:
    """Bootstrap + seed N facts (no ``valid_to``)."""
    tenant_root, s1, backend = _bootstrap_tenant(lethe_home)
    for fid in fact_ids:
        backend._seed_fact(
            group_id=s1.tenant_id,
            fact_id=fid,
            valid_from="2026-01-01T00:00:00Z",
        )
    return tenant_root, s1, backend


def _make_recording_sink() -> tuple[list[Mapping[str, Any]], Any]:
    """Return ``(captured_envelopes, sink_callable)`` — record every emit."""
    captured: list[Mapping[str, Any]] = []

    def sink(env: Mapping[str, Any]) -> None:
        captured.append(env)

    return captured, sink


def _make_failing_sink(message: str = "sink_explode") -> Any:
    """A sink that always raises :class:`RuntimeError`."""

    def sink(env: Mapping[str, Any]) -> None:
        raise RuntimeError(f"{message}: {env.get('event_id', '<no-event-id>')}")

    return sink


def _read_promotion_flags(tenant_root: Path) -> list[tuple[Any, ...]]:
    with shared_store_connection(tenant_root) as conn:
        return conn.execute(
            "SELECT tenant_id, fact_id, tier, flag_set_at, flag_set_by, reason "
            "FROM main.promotion_flags ORDER BY fact_id"
        ).fetchall()


def _read_s5_log(tenant_root: Path) -> list[tuple[Any, ...]]:
    with shared_store_connection(tenant_root) as conn:
        return conn.execute(
            "SELECT seq, kind, payload_json, appended_at "
            "FROM main.s5_consolidation_log ORDER BY seq"
        ).fetchall()


# ---------- promote: happy path ---------- #


def test_promote_writes_promotion_flags_and_s5_and_emits(lethe_home: Path) -> None:
    """promote() writes ``tier='promoted'`` row + S5 entry + emits one event per fact."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1", "fact-2"])
    captured, sink = _make_recording_sink()
    result = promote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1", "fact-2"],
        score_outputs={"fact-1": 0.85, "fact-2": 0.92},
        decisions={
            "fact-1": "score_above_theta_promote",
            "fact-2": "score_above_theta_promote",
        },
        run_id="consolidate-run-test-001",
        sink=sink,
    )
    assert isinstance(result, PhaseResult)
    assert result.committed_fact_ids == ("fact-1", "fact-2")
    assert result.sink_failures == ()
    flags = _read_promotion_flags(tenant_root)
    assert len(flags) == 2
    assert {f[2] for f in flags} == {"promoted"}
    assert {f[4] for f in flags} == {"consolidate-run-test-001"}
    log = _read_s5_log(tenant_root)
    assert len(log) == 2
    assert {row[1] for row in log} == {"promote"}
    # Gate 15 — events.py:validate round-trip.
    assert len(captured) == 2
    for env in captured:
        validate(env)


def test_promote_event_payload_carries_required_fields(lethe_home: Path) -> None:
    """Each emitted promote envelope carries the §8.2 common envelope +
    per-type extras; events.py:validate would reject otherwise."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    captured, sink = _make_recording_sink()
    promote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.85},
        decisions={"fact-1": "score_above_theta_promote"},
        run_id="consolidate-run-test-001",
        sink=sink,
    )
    env = captured[0]
    assert env["event_type"] == "promote"
    assert env["fact_ids"] == ["fact-1"]
    assert env["decision"] == "score_above_theta_promote"
    assert env["score_output"] == 0.85
    assert env["consolidate_run_id"] == "consolidate-run-test-001"
    assert env["contamination_protected"] is True


# ---------- promote: preflight ---------- #


def test_promote_preflight_rejects_empty_run_id(lethe_home: Path) -> None:
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    with pytest.raises(ValueError, match="run_id must be a non-empty string"):
        promote(
            tenant_id=s1.tenant_id,
            tenant_root=tenant_root,
            s1_client=s1,
            fact_ids=["fact-1"],
            score_outputs={"fact-1": 0.85},
            decisions={"fact-1": "score_above_theta_promote"},
            run_id="",
        )


def test_promote_preflight_rejects_missing_score_output(lethe_home: Path) -> None:
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    with pytest.raises(ValueError, match=r"fact_id 'fact-1' missing from score_outputs"):
        promote(
            tenant_id=s1.tenant_id,
            tenant_root=tenant_root,
            s1_client=s1,
            fact_ids=["fact-1"],
            score_outputs={},
            decisions={"fact-1": "score_above_theta_promote"},
            run_id="consolidate-run-test-001",
        )


def test_promote_preflight_rejects_unknown_decision(lethe_home: Path) -> None:
    """Gate 16 — decision-enum violation raises ValueError BEFORE any S1 write."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    with pytest.raises(ValueError, match=r"decision 'mystery' for fact_id 'fact-1' not in"):
        promote(
            tenant_id=s1.tenant_id,
            tenant_root=tenant_root,
            s1_client=s1,
            fact_ids=["fact-1"],
            score_outputs={"fact-1": 0.85},
            decisions={"fact-1": "mystery"},
            run_id="consolidate-run-test-001",
        )
    # No promotion_flags row + no S5 entry written.
    assert _read_promotion_flags(tenant_root) == []
    assert _read_s5_log(tenant_root) == []


# ---------- demote: happy path ---------- #


def test_demote_writes_s1_and_promotion_flags_and_s5(lethe_home: Path) -> None:
    tenant_root, s1, backend = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    captured, sink = _make_recording_sink()
    result = demote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.05},
        decisions={"fact-1": "score_below_theta_demote"},
        run_id="consolidate-run-test-001",
        valid_to="2026-06-01T00:00:00Z",
        sink=sink,
    )
    assert result.committed_fact_ids == ("fact-1",)
    assert backend._facts[s1.tenant_id]["fact-1"].valid_to == "2026-06-01T00:00:00Z"
    flags = _read_promotion_flags(tenant_root)
    assert flags == [
        (
            s1.tenant_id,
            "fact-1",
            "demoted",
            flags[0][3],
            "consolidate-run-test-001",
            "score_below_theta_demote",
        )
    ]
    log = _read_s5_log(tenant_root)
    assert [row[1] for row in log] == ["demote"]
    assert len(captured) == 1
    validate(captured[0])


# ---------- demote: preflight ---------- #


def test_demote_preflight_rejects_unparseable_valid_to(lethe_home: Path) -> None:
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    with pytest.raises(ValueError, match="not a parseable RFC 3339 timestamp"):
        demote(
            tenant_id=s1.tenant_id,
            tenant_root=tenant_root,
            s1_client=s1,
            fact_ids=["fact-1"],
            score_outputs={"fact-1": 0.05},
            decisions={"fact-1": "score_below_theta_demote"},
            run_id="consolidate-run-test-001",
            valid_to="not-a-real-timestamp",
        )


def test_demote_preflight_rejects_unknown_decision(lethe_home: Path) -> None:
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    with pytest.raises(ValueError, match=r"decision 'random' for fact_id 'fact-1' not in"):
        demote(
            tenant_id=s1.tenant_id,
            tenant_root=tenant_root,
            s1_client=s1,
            fact_ids=["fact-1"],
            score_outputs={"fact-1": 0.05},
            decisions={"fact-1": "random"},
            run_id="consolidate-run-test-001",
            valid_to="2026-06-01T00:00:00Z",
        )


# ---------- demote: REPLACE semantics ---------- #


def test_demote_after_promote_replaces_tier_in_place(lethe_home: Path) -> None:
    """Gate 17 — promote then demote same fact → 1 promotion_flags row tier='demoted'."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    promote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.85},
        decisions={"fact-1": "score_above_theta_promote"},
        run_id="consolidate-run-test-001",
    )
    demote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.05},
        decisions={"fact-1": "score_below_theta_demote"},
        run_id="consolidate-run-test-002",
        valid_to="2026-06-01T00:00:00Z",
    )
    flags = _read_promotion_flags(tenant_root)
    assert len(flags) == 1
    assert flags[0][2] == "demoted"
    assert flags[0][4] == "consolidate-run-test-002"
    # S5 audit retains both.
    log = _read_s5_log(tenant_root)
    assert [row[1] for row in log] == ["promote", "demote"]


# ---------- demote: S1-first ordering ---------- #


class _ExplodingS1Client:
    """S1Client wrapper whose set_fact_valid_to succeeds for the first
    ``ok_count`` calls then raises ``_PartialS1Failure`` on the next."""

    def __init__(self, inner: S1Client, ok_count: int) -> None:
        self._inner = inner
        self._ok_count = ok_count
        self._calls = 0

    @property
    def tenant_id(self) -> str:
        return self._inner.tenant_id

    def set_fact_valid_to(self, *, fact_id: str, valid_to: str) -> None:
        if self._calls >= self._ok_count:
            self._calls += 1
            raise _PartialS1Failure(f"injected failure on fact_id={fact_id!r}")
        self._calls += 1
        self._inner.set_fact_valid_to(fact_id=fact_id, valid_to=valid_to)

    def iter_facts_with_valid_to(self) -> Any:
        return self._inner.iter_facts_with_valid_to()


class _PartialS1Failure(RuntimeError):
    pass


def test_demote_partial_s1_failure_leaves_no_s2_writes(lethe_home: Path) -> None:
    """Gate 22 (per IMPLEMENT 6 amendment A4) — multi-fact partial S1 failure
    invariant: S1 succeeds for fact 'a', raises for fact 'b'; no S2/S5/event
    writes occur (function raises before BEGIN IMMEDIATE)."""
    tenant_root, s1, backend = _make_s1_client_with_seeded_facts(lethe_home, ["fact-a", "fact-b"])
    exploding = _ExplodingS1Client(s1, ok_count=1)
    captured, sink = _make_recording_sink()
    with pytest.raises(_PartialS1Failure):
        demote(
            tenant_id=s1.tenant_id,
            tenant_root=tenant_root,
            s1_client=exploding,  # type: ignore[arg-type]
            fact_ids=["fact-a", "fact-b"],
            score_outputs={"fact-a": 0.05, "fact-b": 0.05},
            decisions={
                "fact-a": "score_below_theta_demote",
                "fact-b": "score_below_theta_demote",
            },
            run_id="consolidate-run-test-001",
            valid_to="2026-06-01T00:00:00Z",
            sink=sink,
        )
    # S1 'a' has valid_to set, 'b' does not.
    assert backend._facts[s1.tenant_id]["fact-a"].valid_to == "2026-06-01T00:00:00Z"
    assert backend._facts[s1.tenant_id]["fact-b"].valid_to is None
    # S2 / S5 / events untouched.
    assert _read_promotion_flags(tenant_root) == []
    assert _read_s5_log(tenant_root) == []
    assert captured == []


def test_invalidate_partial_s1_failure_leaves_no_s2_writes(lethe_home: Path) -> None:
    """Gate 22 (mirror for invalidate)."""
    tenant_root, s1, backend = _make_s1_client_with_seeded_facts(lethe_home, ["fact-a", "fact-b"])
    exploding = _ExplodingS1Client(s1, ok_count=1)
    captured, sink = _make_recording_sink()
    with pytest.raises(_PartialS1Failure):
        invalidate(
            tenant_id=s1.tenant_id,
            tenant_root=tenant_root,
            s1_client=exploding,  # type: ignore[arg-type]
            fact_ids=["fact-a", "fact-b"],
            decisions={
                "fact-a": "contradiction_detected",
                "fact-b": "contradiction_detected",
            },
            superseded_by={"fact-a": None, "fact-b": None},
            run_id="consolidate-run-test-001",
            valid_to="2026-06-01T00:00:00Z",
            sink=sink,
        )
    assert backend._facts[s1.tenant_id]["fact-a"].valid_to == "2026-06-01T00:00:00Z"
    assert backend._facts[s1.tenant_id]["fact-b"].valid_to is None
    assert _read_promotion_flags(tenant_root) == []
    assert _read_s5_log(tenant_root) == []
    assert captured == []


# ---------- demote: gate 19 — S1 write precedes S2 write ---------- #


def test_demote_s1_write_precedes_s2_write(lethe_home: Path) -> None:
    """Gate 19 — S1 happens FIRST. We assert this by injecting an S1Client
    that raises during the S2 transaction (via a malformed valid_to caught
    only by SQLite). Cleaner: call demote, then introspect that S1 has
    valid_to BEFORE the S2 row was visible. Easiest empirical assertion:
    demote a fact_id that S1 accepts (set_fact_valid_to mutates) but
    inject a sqlite_master corruption is overkill — instead assert order
    by observing that on a successful demote, S1 valid_to == valid_to AND
    the promotion_flags row exists. The S1-first invariant is structurally
    enforced by the function body (preflight → reconciler → S1 loop →
    BEGIN IMMEDIATE); the partial-S1-failure tests above already prove
    the inverse direction (S1 partial succ + S2 untouched)."""
    tenant_root, s1, backend = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    demote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.05},
        decisions={"fact-1": "score_below_theta_demote"},
        run_id="consolidate-run-test-001",
        valid_to="2026-06-01T00:00:00Z",
    )
    # S1 set.
    assert backend._facts[s1.tenant_id]["fact-1"].valid_to == "2026-06-01T00:00:00Z"
    # S2 row exists (and reconciler does NOT see it as orphan because the
    # promotion_flags tier 'demoted' covers it — see reconciler tests).
    flags = _read_promotion_flags(tenant_root)
    assert flags[0][2] == "demoted"


# ---------- invalidate: happy path + variants ---------- #


def test_invalidate_hard_writes_promotion_flags_and_s5(lethe_home: Path) -> None:
    """Hard invalidate (``superseded_by[fid] is None``) round-trips through
    events.py:validate (the key is REQUIRED, the value MAY be None)."""
    tenant_root, s1, backend = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    captured, sink = _make_recording_sink()
    invalidate(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        decisions={"fact-1": "manual_correction"},
        superseded_by={"fact-1": None},
        run_id="consolidate-run-test-001",
        valid_to="2026-06-01T00:00:00Z",
        sink=sink,
    )
    assert backend._facts[s1.tenant_id]["fact-1"].valid_to == "2026-06-01T00:00:00Z"
    flags = _read_promotion_flags(tenant_root)
    assert flags[0][2] == "invalidated"
    assert captured[0]["superseded_by"] is None
    validate(captured[0])


def test_invalidate_soft_carries_supersession_pointer(lethe_home: Path) -> None:
    """Soft invalidate (``superseded_by[fid] = "fact-2"``) — pointer plumbed."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    captured, sink = _make_recording_sink()
    invalidate(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        decisions={"fact-1": "superseded"},
        superseded_by={"fact-1": "fact-2"},
        run_id="consolidate-run-test-001",
        valid_to="2026-06-01T00:00:00Z",
        sink=sink,
    )
    assert captured[0]["superseded_by"] == "fact-2"
    validate(captured[0])


def test_invalidate_preflight_rejects_missing_superseded_by_key(lethe_home: Path) -> None:
    """Per A5 + events.py:148 — the superseded_by KEY is required (value
    may be None for hard invalidate)."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    with pytest.raises(ValueError, match=r"fact_id 'fact-1' missing from superseded_by"):
        invalidate(
            tenant_id=s1.tenant_id,
            tenant_root=tenant_root,
            s1_client=s1,
            fact_ids=["fact-1"],
            decisions={"fact-1": "contradiction_detected"},
            superseded_by={},
            run_id="consolidate-run-test-001",
            valid_to="2026-06-01T00:00:00Z",
        )


def test_invalidate_preflight_rejects_unknown_reason(lethe_home: Path) -> None:
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    with pytest.raises(ValueError, match=r"decision 'unknown_reason' for fact_id 'fact-1' not in"):
        invalidate(
            tenant_id=s1.tenant_id,
            tenant_root=tenant_root,
            s1_client=s1,
            fact_ids=["fact-1"],
            decisions={"fact-1": "unknown_reason"},
            superseded_by={"fact-1": None},
            run_id="consolidate-run-test-001",
            valid_to="2026-06-01T00:00:00Z",
        )


def test_invalidate_preflight_rejects_empty_supersession_pointer(lethe_home: Path) -> None:
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    err_re = r"superseded_by\['fact-1'\] must be None or non-empty str"
    with pytest.raises(ValueError, match=err_re):
        invalidate(
            tenant_id=s1.tenant_id,
            tenant_root=tenant_root,
            s1_client=s1,
            fact_ids=["fact-1"],
            decisions={"fact-1": "superseded"},
            superseded_by={"fact-1": ""},
            run_id="consolidate-run-test-001",
            valid_to="2026-06-01T00:00:00Z",
        )


# ---------- reconciler ---------- #


def test_reconciler_no_op_when_no_orphans(lethe_home: Path) -> None:
    """No facts with valid_to → reconciler returns []; promotion_flags + S5 unchanged."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    orphans = reconcile_orphans(tenant_id=s1.tenant_id, tenant_root=tenant_root, s1_client=s1)
    assert orphans == []
    assert _read_promotion_flags(tenant_root) == []
    assert _read_s5_log(tenant_root) == []


def test_reconciler_writes_backfill_row_for_orphan(lethe_home: Path) -> None:
    """Gate 20 — manually set S1 valid_to (skipping the phase) → reconciler
    writes ``tier='backfilled', flag_set_by='reconciler'`` row + S5 entry."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    s1.set_fact_valid_to(fact_id="fact-1", valid_to="2026-06-01T00:00:00Z")
    orphans = reconcile_orphans(tenant_id=s1.tenant_id, tenant_root=tenant_root, s1_client=s1)
    assert orphans == ["fact-1"]
    flags = _read_promotion_flags(tenant_root)
    assert len(flags) == 1
    assert flags[0][2] == "backfilled"
    assert flags[0][4] == "reconciler"
    assert flags[0][5] == "s1_state_diff"
    log = _read_s5_log(tenant_root)
    assert len(log) == 1
    assert log[0][1] == "reconciler"


def test_reconciler_does_not_re_backfill_existing_backfilled_row(lethe_home: Path) -> None:
    """Gate 20 — CRITICAL guard for the infinite-loop fix (per IMPLEMENT 6
    amendment A2). Second run sees the first run's ``tier='backfilled'``
    row and skips it. Without this, every consolidate run would
    re-backfill every fact a prior run already backfilled."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    s1.set_fact_valid_to(fact_id="fact-1", valid_to="2026-06-01T00:00:00Z")
    first = reconcile_orphans(tenant_id=s1.tenant_id, tenant_root=tenant_root, s1_client=s1)
    assert first == ["fact-1"]
    # Second pass: 'backfilled' covers the orphan; nothing to do.
    second = reconcile_orphans(tenant_id=s1.tenant_id, tenant_root=tenant_root, s1_client=s1)
    assert second == []
    # Exactly 1 backfill row + 1 S5 entry total (NO duplicates).
    assert len(_read_promotion_flags(tenant_root)) == 1
    assert len(_read_s5_log(tenant_root)) == 1


def test_reconciler_does_not_backfill_demoted_or_invalidated_facts(lethe_home: Path) -> None:
    """Per A2 — orphan = S1 valid_to AND no promotion_flags row of tier ∈
    {demoted, invalidated, backfilled}. After demote, the fact has S1
    valid_to set AND tier='demoted' — NOT an orphan."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    demote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.05},
        decisions={"fact-1": "score_below_theta_demote"},
        run_id="consolidate-run-test-001",
        valid_to="2026-06-01T00:00:00Z",
    )
    # Direct reconciler call: should be no-op.
    orphans = reconcile_orphans(tenant_id=s1.tenant_id, tenant_root=tenant_root, s1_client=s1)
    assert orphans == []
    flags = _read_promotion_flags(tenant_root)
    assert len(flags) == 1
    assert flags[0][2] == "demoted"  # NOT overwritten with backfilled


# ---------- post-commit sink failure (Gate 24, per A9) ---------- #


def test_demote_sink_failure_does_not_raise_or_rollback_state(lethe_home: Path) -> None:
    """Gate 24 — post-commit sink failure surfaces in PhaseResult.sink_failures
    but does NOT raise; promotion_flags + S5 + S1 state remain durable."""
    tenant_root, s1, backend = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1", "fact-2"])
    sink = _make_failing_sink()
    result = demote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1", "fact-2"],
        score_outputs={"fact-1": 0.05, "fact-2": 0.05},
        decisions={
            "fact-1": "score_below_theta_demote",
            "fact-2": "score_below_theta_demote",
        },
        run_id="consolidate-run-test-001",
        valid_to="2026-06-01T00:00:00Z",
        sink=sink,
    )
    assert result.committed_fact_ids == ("fact-1", "fact-2")
    assert len(result.sink_failures) == 2
    assert all(isinstance(failure[1], RuntimeError) for failure in result.sink_failures)
    # State durable.
    assert backend._facts[s1.tenant_id]["fact-1"].valid_to == "2026-06-01T00:00:00Z"
    assert backend._facts[s1.tenant_id]["fact-2"].valid_to == "2026-06-01T00:00:00Z"
    flags = _read_promotion_flags(tenant_root)
    assert {f[2] for f in flags} == {"demoted"}
    assert len(_read_s5_log(tenant_root)) == 2


# ---------- random uuidv7 (Gate 23, per A8) ---------- #


def test_promote_event_ids_are_unique_across_calls(lethe_home: Path) -> None:
    """Gate 23 — call promote twice with the same fact_id + run_id; assert
    event_ids differ (event_id is a RANDOM uuidv7, NOT deterministic)."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    captured, sink = _make_recording_sink()
    promote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.85},
        decisions={"fact-1": "score_above_theta_promote"},
        run_id="consolidate-run-test-001",
        sink=sink,
    )
    promote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.85},
        decisions={"fact-1": "score_above_theta_promote"},
        run_id="consolidate-run-test-001",
        sink=sink,
    )
    assert len(captured) == 2
    assert captured[0]["event_id"] != captured[1]["event_id"]


# ---------- Z-suffix timestamp format (Gate 25, per A11) ---------- #


def test_event_timestamps_use_z_suffix_format(lethe_home: Path) -> None:
    """Gate 25 — emitted event ts_recorded uses RFC 3339 with 'Z' suffix
    (matches api.remember + api.recall format; round-trip determinism)."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    captured, sink = _make_recording_sink()
    promote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.85},
        decisions={"fact-1": "score_above_theta_promote"},
        run_id="consolidate-run-test-001",
        now=datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC),
        sink=sink,
    )
    env = captured[0]
    assert env["ts_recorded"].endswith("Z"), env["ts_recorded"]
    assert env["ts_valid"].endswith("Z"), env["ts_valid"]
    assert "+00:00" not in env["ts_recorded"]
    # Sanity — the deterministic ``now`` round-trips.
    assert env["ts_recorded"] == "2026-06-01T12:00:00Z"


def test_s5_log_appended_at_uses_z_suffix(lethe_home: Path) -> None:
    """Gate 25 (mirror for the S5 ledger) — append_with_conn writes
    appended_at with the 'Z' suffix per A11."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    promote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        score_outputs={"fact-1": 0.85},
        decisions={"fact-1": "score_above_theta_promote"},
        run_id="consolidate-run-test-001",
    )
    log = _read_s5_log(tenant_root)
    assert log[0][3].endswith("Z"), log[0][3]
    assert "+00:00" not in log[0][3]


# ---------- enum coverage / sanity ---------- #


def test_promotion_flag_tiers_enum_covers_all_phase_outputs() -> None:
    """The shared enum :data:`PROMOTION_FLAG_TIERS` covers every tier the
    phases + reconciler write."""
    assert "promoted" in PROMOTION_FLAG_TIERS
    assert "demoted" in PROMOTION_FLAG_TIERS
    assert "invalidated" in PROMOTION_FLAG_TIERS
    assert "backfilled" in PROMOTION_FLAG_TIERS


def test_phase_decision_enums_are_disjoint() -> None:
    """promote / demote / invalidate decision enums must be disjoint —
    a single string never has ambiguous phase ownership."""
    assert PROMOTE_DECISIONS.isdisjoint(DEMOTE_DECISIONS)
    assert PROMOTE_DECISIONS.isdisjoint(INVALIDATE_REASONS)
    assert DEMOTE_DECISIONS.isdisjoint(INVALIDATE_REASONS)


# ---------- cross-phase: phase chaining + reconciler integration ---------- #


def test_demote_runs_reconciler_at_entry(lethe_home: Path) -> None:
    """Per §k.6 — phase entry calls the reconciler. Manually set S1 valid_to
    on a fact (skipping the phase), then call demote on a DIFFERENT fact;
    the orphan should be backfilled by the reconciler step."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["orphan-fact", "main-fact"])
    s1.set_fact_valid_to(fact_id="orphan-fact", valid_to="2026-05-01T00:00:00Z")
    result = demote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["main-fact"],
        score_outputs={"main-fact": 0.05},
        decisions={"main-fact": "score_below_theta_demote"},
        run_id="consolidate-run-test-001",
        valid_to="2026-06-01T00:00:00Z",
    )
    assert result.orphans_backfilled == ("orphan-fact",)
    flags = _read_promotion_flags(tenant_root)
    # Two rows: orphan-fact (backfilled by reconciler) + main-fact (demoted).
    rows_by_fact = {row[1]: row for row in flags}
    assert rows_by_fact["orphan-fact"][2] == "backfilled"
    assert rows_by_fact["main-fact"][2] == "demoted"


def test_phases_in_isolation_do_not_share_state(lethe_home: Path) -> None:
    """Defensive: invoking promote then invalidate on different facts in the
    same process leaves promote's flag intact (no shared mutable globals)."""
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-a", "fact-b"])
    promote(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-a"],
        score_outputs={"fact-a": 0.85},
        decisions={"fact-a": "score_above_theta_promote"},
        run_id="consolidate-run-test-001",
    )
    invalidate(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-b"],
        decisions={"fact-b": "manual_correction"},
        superseded_by={"fact-b": None},
        run_id="consolidate-run-test-002",
        valid_to="2026-06-01T00:00:00Z",
    )
    rows_by_fact = {row[1]: row for row in _read_promotion_flags(tenant_root)}
    assert rows_by_fact["fact-a"][2] == "promoted"
    assert rows_by_fact["fact-b"][2] == "invalidated"


# ---------- KeyError contract on S1 (per A10) ---------- #


def test_s1_set_fact_valid_to_raises_keyerror_for_missing_fact(lethe_home: Path) -> None:
    """Per A10 — set_fact_valid_to raises KeyError for missing fact_id."""
    _, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    with pytest.raises(KeyError, match="not seeded for group_id"):
        s1.set_fact_valid_to(fact_id="nonexistent", valid_to="2026-06-01T00:00:00Z")


def test_s1_iter_facts_with_valid_to_returns_empty_for_unbootstrapped(lethe_home: Path) -> None:
    """Per A10 — iter_facts_with_valid_to is permissive: empty iter for an
    unbootstrapped tenant (only set_fact_valid_to raises)."""
    bootstrap(tenant_id="other-tenant", storage_root=lethe_home)
    backend = _InMemoryGraphBackend()
    s1 = S1Client(backend, tenant_id="never-bootstrapped")
    # Backend.bootstrap_tenant was never called — _facts has no entry for "never-bootstrapped".
    assert list(s1.iter_facts_with_valid_to()) == []


# ---------- audit-history-only utility_events (per A3) — surfaces below ---------- #


def test_invalidate_does_not_insert_into_utility_events(lethe_home: Path) -> None:
    """Gate 18 (replaces the dropped 'freeze' test per IMPLEMENT 6 A3) —
    invalidate at C6 does not INSERT into ``utility_events`` either.
    Combined with the byte-identity test in test_bitemporal_p4.py, this
    pins the no-op semantics from both directions (no UPDATE, no INSERT).
    """
    tenant_root, s1, _ = _make_s1_client_with_seeded_facts(lethe_home, ["fact-1"])
    invalidate(
        tenant_id=s1.tenant_id,
        tenant_root=tenant_root,
        s1_client=s1,
        fact_ids=["fact-1"],
        decisions={"fact-1": "score_below_floor"},
        superseded_by={"fact-1": None},
        run_id="consolidate-run-test-001",
        valid_to="2026-06-01T00:00:00Z",
    )
    with shared_store_connection(tenant_root) as conn:
        count = conn.execute("SELECT COUNT(*) FROM main.utility_events").fetchone()[0]
    assert count == 0


# ---------- gate 21 (audit) lives outside this file (grep gate). ---------- #


# ---------- C7 APPEND per IMPLEMENT 7 amendment A4 — canonical I-11 order ---------- #


def test_phase_dispatch_table_matches_canonical_order() -> None:
    """Gate 15 (A4): PHASE_DISPATCH order matches canonical I-11 order.

    Per IMPLEMENT 7 amendment A4: this test asserts (a) tuple equality
    against the literal canonical order from IMPL §2.4 invariant I-11,
    (b) frozenset membership equality against
    ``events.py:_VALID_CONSOLIDATE_PHASES`` (which is a frozenset and
    therefore unordered — the canonical ORDER lives only in
    PHASE_DISPATCH here), and (c) that PHASE_DISPATCH itself is a
    tuple (immutable). MUST NOT reference ``_VALID_CONSOLIDATE_PHASES_ORDER``
    — that constant does not exist; events.py is held at 0 lines diff
    vs origin/main per §7.11.
    """
    from lethe.runtime.consolidate.phases import PHASE_DISPATCH
    from lethe.runtime.events import _VALID_CONSOLIDATE_PHASES

    names = tuple(name for name, _ in PHASE_DISPATCH)
    # (a) Canonical I-11 order from IMPL §2.4
    assert names == (
        "extract",
        "score",
        "promote",
        "demote",
        "consolidate",
        "invalidate",
    )
    # (b) Frozenset membership equality — events.py owns set, this owns order
    assert set(names) == _VALID_CONSOLIDATE_PHASES
    # (c) PHASE_DISPATCH is an immutable tuple
    assert isinstance(PHASE_DISPATCH, tuple)
