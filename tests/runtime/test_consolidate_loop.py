"""Consolidate loop orchestration tests for P4 commit 7.

Covers the public + private surfaces of :mod:`.loop` end-to-end:

- 6 phase events fire in canonical order (gate 17, A4 carry).
- ``ConsolidateRunResult.skip_reason`` distinguishes
  ``"gate_not_elapsed"`` vs ``"lock_held"`` (A7 — gate 31).
- ``LoopPhaseResult.status`` reflects per-phase outcome (A8 — gate 32).
- Heartbeat called between phases ONLY (not after the final phase) —
  exactly 5 calls in a 6-phase happy path (A3 — gate 28).
- Phase-failed mid-loop logs S5 ``phase_failed`` + remaining phases
  marked ``"skipped"`` + lock cleared via ``clear_lock`` (NOT
  ``mark_success_and_release``) + ``last_run_at`` unchanged (A1 —
  gate 26 + 22).
- Lock-lost mid-loop aborts gracefully + ``last_run_at`` unchanged
  + S5 ``lock_lost`` row (gate 21).
- Lock-lost mid-loop preserves already-committed phase work (A11
  durability invariant — gate 33).
- ``run_one_consolidate`` public surface has NO test seam (A10) —
  every dispatch-injection test calls
  :func:`_run_one_consolidate_with_dispatch` directly.

LETHE_HOME isolation honored via the conftest ``lethe_home`` fixture.
No new deps.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from lethe.runtime import bootstrap
from lethe.runtime import events as _events_mod
from lethe.runtime.consolidate import (
    PHASE_DISPATCH,
    ConsolidateRun,
    ConsolidateRunResult,
    LoopPhaseResult,
    NullEmbedder,
    acquire_lock,
    force_clear_lock,
    run_one_consolidate,
)
from lethe.runtime.consolidate._reconciler import PhaseResult
from lethe.runtime.consolidate.loop import (
    _run_one_consolidate_with_dispatch,
)
from lethe.runtime.consolidate.scheduler import (
    GATE_INTERVAL_SECONDS,
)
from lethe.store import shared_store_connection
from lethe.store.s1_graph.client import S1Client, _InMemoryGraphBackend
from lethe.store.s2_meta.schema import S5_LOG_TABLE_NAME
from lethe.store.s3_vec.client import S3Client

TENANT = "smoke-tenant"


# ---------- bootstrap helpers ---------- #


def _bootstrap(lethe_home: Path) -> tuple[Path, S1Client, S3Client, NullEmbedder]:
    bootstrap(tenant_id=TENANT, storage_root=lethe_home)
    tenant_root = lethe_home / "tenants" / TENANT
    backend = _InMemoryGraphBackend()
    s1 = S1Client(backend, tenant_id=TENANT)
    s1.bootstrap()
    s3 = S3Client(tenant_root=tenant_root)
    embedder = NullEmbedder()
    return tenant_root, s1, s3, embedder


def _empty_phase_result() -> PhaseResult:
    return PhaseResult(
        committed_fact_ids=(),
        sink_failures=(),
        orphans_backfilled=(),
    )


def _make_recording_dispatch(
    *,
    record: list[str],
    failures: dict[str, Exception] | None = None,
) -> tuple[tuple[str, Callable[[ConsolidateRun], PhaseResult]], ...]:
    """Build a dispatch tuple that records per-phase invocations.

    ``failures`` maps ``phase_name → exception`` to inject a phase
    failure mid-loop (gate 22 / A1).
    """
    failures = failures or {}

    def make_phase(name: str) -> Callable[[ConsolidateRun], PhaseResult]:
        def _phase(_ctx: ConsolidateRun) -> PhaseResult:
            record.append(name)
            if name in failures:
                raise failures[name]
            return _empty_phase_result()

        return _phase

    return tuple((name, make_phase(name)) for name, _ in PHASE_DISPATCH)


def _consolidation_state_row(tenant_root: Path) -> dict[str, Any] | None:
    with shared_store_connection(tenant_root) as conn:
        cursor = conn.execute(
            "SELECT lock_token, last_run_at FROM main.consolidation_state WHERE tenant_id = ?",
            (TENANT,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return {"lock_token": row[0], "last_run_at": row[1]}


def _s5_rows_of_kind(tenant_root: Path, kind: str) -> list[dict[str, Any]]:
    with shared_store_connection(tenant_root) as conn:
        cursor = conn.execute(
            f"SELECT kind, payload_json FROM main.{S5_LOG_TABLE_NAME} "
            f"WHERE kind = ? ORDER BY seq ASC",
            (kind,),
        )
        return [{"kind": r[0], "payload": json.loads(r[1])} for r in cursor.fetchall()]


# ---------- (1) happy path: 6 phases, 5 heartbeats, mark_success ---------- #


def test_run_one_consolidate_emits_six_phase_events_at_p4(lethe_home: Path) -> None:
    """Gate 17: 6 ``consolidate_phase`` envelopes fire in canonical order."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    captured: list[Mapping[str, Any]] = []

    def sink(env: Mapping[str, Any]) -> None:
        captured.append(dict(env))

    result = run_one_consolidate(
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
        sink=sink,
    )

    assert result.skipped is False
    assert result.lock_acquired is True
    assert len(result.phase_results) == 6
    # All 6 envelopes arrived at the sink in canonical order
    assert [str(e["phase_name"]) for e in captured] == [
        "extract",
        "score",
        "promote",
        "demote",
        "consolidate",
        "invalidate",
    ]
    # Gate 16: every envelope passes events.validate (emit() validates
    # internally per events.py:emit contract)
    for env in captured:
        _events_mod.validate(env)
        assert env["event_type"] == "consolidate_phase"
        assert env["consolidate_run_id"] == result.run_id


def test_loop_does_not_heartbeat_after_final_phase(
    lethe_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gate 28 (A3): exactly 5 heartbeat calls in a 6-phase happy path."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    record: list[str] = []
    dispatch = _make_recording_dispatch(record=record)

    heartbeat_calls = 0

    def _spy_heartbeat(**_kwargs: Any) -> bool:
        nonlocal heartbeat_calls
        heartbeat_calls += 1
        return True

    monkeypatch.setattr("lethe.runtime.consolidate.loop.heartbeat", _spy_heartbeat)
    result = _run_one_consolidate_with_dispatch(
        dispatch,
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
    )

    assert result.skipped is False
    assert result.lock_acquired is True
    assert record == [
        "extract",
        "score",
        "promote",
        "demote",
        "consolidate",
        "invalidate",
    ]
    assert heartbeat_calls == 5  # NOT 6 — A3 invariant


def test_happy_path_marks_success_and_advances_last_run_at(lethe_home: Path) -> None:
    """A1: clean 6-phase run uses mark_success_and_release → last_run_at set."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    fixed_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    record: list[str] = []
    dispatch = _make_recording_dispatch(record=record)

    result = _run_one_consolidate_with_dispatch(
        dispatch,
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
        now=fixed_now,
    )

    assert result.skipped is False
    assert result.lock_lost is False
    assert result.error is None
    row = _consolidation_state_row(tenant_root)
    assert row is not None
    assert row["lock_token"] is None
    assert row["last_run_at"] == "2026-06-01T12:00:00Z"


def test_run_id_is_random_uuidv7(lethe_home: Path) -> None:
    """run_id is a uuidv7 string and varies across runs."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    record_a: list[str] = []
    result_a = _run_one_consolidate_with_dispatch(
        _make_recording_dispatch(record=record_a),
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
    )
    # Force the gate to elapse so the second run is not skipped
    after_gate = datetime.now(UTC) + timedelta(seconds=GATE_INTERVAL_SECONDS + 1)
    record_b: list[str] = []
    result_b = _run_one_consolidate_with_dispatch(
        _make_recording_dispatch(record=record_b),
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
        now=after_gate,
    )
    assert isinstance(result_a.run_id, str) and len(result_a.run_id) == 36
    assert result_a.run_id[14] == "7"
    assert isinstance(result_b.run_id, str)
    assert result_a.run_id != result_b.run_id


# ---------- (2) skip semantics — A7 distinguish gate vs lock_held ---------- #


def test_skipped_distinguishes_gate_vs_lock_held(lethe_home: Path) -> None:
    """A7 / Gate 31: skip_reason differs for gate-not-elapsed vs lock-held."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    record: list[str] = []

    # First run completes successfully → last_run_at set
    first = _run_one_consolidate_with_dispatch(
        _make_recording_dispatch(record=record),
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
        now=base_now,
    )
    assert first.skipped is False

    # Second run BEFORE gate elapses → skipped=True, gate_not_elapsed
    soon = base_now + timedelta(seconds=60)
    skipped_gate = _run_one_consolidate_with_dispatch(
        _make_recording_dispatch(record=[]),
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
        now=soon,
    )
    assert skipped_gate.skipped is True
    assert skipped_gate.skip_reason == "gate_not_elapsed"
    assert skipped_gate.lock_acquired is False
    assert skipped_gate.error is None
    assert skipped_gate.run_id is None
    assert skipped_gate.phase_results == ()

    # Now: hold the lock externally, then call after gate elapses → skip_reason=lock_held
    after_gate = base_now + timedelta(seconds=GATE_INTERVAL_SECONDS + 1)
    acquire_lock(tenant_id=TENANT, tenant_root=tenant_root, now=after_gate)
    skipped_lock = _run_one_consolidate_with_dispatch(
        _make_recording_dispatch(record=[]),
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
        now=after_gate + timedelta(seconds=1),
    )
    assert skipped_lock.skipped is True
    assert skipped_lock.skip_reason == "lock_held"
    assert skipped_lock.lock_acquired is False
    assert skipped_lock.error is None


# ---------- (3) phase_failed — A1/A8 — gates 22, 26, 32 ---------- #


def test_loop_logs_phase_failed_and_releases_lock(lethe_home: Path) -> None:
    """Gate 22: phase_failed mid-loop logs S5 + skips remaining + clears lock."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    record: list[str] = []
    boom = RuntimeError("boom")
    dispatch = _make_recording_dispatch(record=record, failures={"promote": boom})

    result = _run_one_consolidate_with_dispatch(
        dispatch,
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
    )

    # phases 1, 2, 3 ran; promote failed; demote/consolidate/invalidate skipped
    assert record == ["extract", "score", "promote"]
    assert result.error is not None
    assert result.error.startswith("promote:RuntimeError")
    assert result.lock_lost is False
    statuses = {pr.phase_name: pr.status for pr in result.phase_results}
    assert statuses == {
        "extract": "succeeded",
        "score": "succeeded",
        "promote": "failed",
        "demote": "skipped",
        "consolidate": "skipped",
        "invalidate": "skipped",
    }
    # S5 phase_failed row written exactly once
    rows = _s5_rows_of_kind(tenant_root, "phase_failed")
    assert len(rows) == 1
    assert rows[0]["payload"]["phase_name"] == "promote"
    assert "RuntimeError" in str(rows[0]["payload"]["error"])
    # Lock cleared (not mark_success), so lock_token is NULL
    state = _consolidation_state_row(tenant_root)
    assert state is not None
    assert state["lock_token"] is None


def test_phase_failed_does_not_advance_last_run_at(lethe_home: Path) -> None:
    """Gate 26 (A1): phase_failed → clear_lock (NOT mark_success) → last_run_at unchanged."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    # Bootstrap with no prior last_run_at (None) → assert it stays None
    pre = _consolidation_state_row(tenant_root)
    pre_last_run_at = None if pre is None else pre["last_run_at"]

    boom = RuntimeError("boom")
    dispatch = _make_recording_dispatch(record=[], failures={"score": boom})
    result = _run_one_consolidate_with_dispatch(
        dispatch,
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
        now=base_now,
    )
    assert result.error is not None
    state = _consolidation_state_row(tenant_root)
    assert state is not None
    assert state["last_run_at"] == pre_last_run_at  # NOT advanced


def test_loop_phase_result_status_reflects_phase_outcome(lethe_home: Path) -> None:
    """Gate 32 (A8): LoopPhaseResult.status maps to succeeded/failed/skipped."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    boom = ValueError("crash")
    dispatch = _make_recording_dispatch(record=[], failures={"demote": boom})
    result = _run_one_consolidate_with_dispatch(
        dispatch,
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
    )
    by_name = {pr.phase_name: pr for pr in result.phase_results}
    # Pre-failure phases succeed, with phase_result populated
    for name in ("extract", "score", "promote"):
        pr = by_name[name]
        assert pr.status == "succeeded"
        assert pr.phase_result is not None
        assert pr.error is None
    # Failed phase has error + phase_result=None
    demote_pr = by_name["demote"]
    assert demote_pr.status == "failed"
    assert demote_pr.phase_result is None
    assert demote_pr.error is not None
    assert "ValueError" in demote_pr.error
    # Skipped phases have no phase_result, no error
    for name in ("consolidate", "invalidate"):
        pr = by_name[name]
        assert pr.status == "skipped"
        assert pr.phase_result is None
        assert pr.error is None


# ---------- (4) lock_lost — gates 21, 33 ---------- #


def test_loop_aborts_on_lock_lost(lethe_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Gate 21: heartbeat False mid-loop → remaining phases skipped + S5 lock_lost row."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    record: list[str] = []
    dispatch = _make_recording_dispatch(record=record)

    # Spy heartbeat: returns True for the first 2 calls, False on the 3rd
    hb_call = 0

    def _spy(**_kwargs: Any) -> bool:
        nonlocal hb_call
        hb_call += 1
        return hb_call < 3  # True, True, False

    monkeypatch.setattr("lethe.runtime.consolidate.loop.heartbeat", _spy)
    result = _run_one_consolidate_with_dispatch(
        dispatch,
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
    )

    # Phases 1, 2, 3 ran (heartbeat False after phase 3 → break before phase 4)
    assert record == ["extract", "score", "promote"]
    assert result.lock_lost is True
    assert result.error is None  # lock_lost is recoverable per A7
    statuses = {pr.phase_name: pr.status for pr in result.phase_results}
    assert statuses == {
        "extract": "succeeded",
        "score": "succeeded",
        "promote": "succeeded",
        "demote": "skipped",
        "consolidate": "skipped",
        "invalidate": "skipped",
    }
    # S5 lock_lost row written
    rows = _s5_rows_of_kind(tenant_root, "lock_lost")
    assert len(rows) == 1
    assert rows[0]["payload"]["phase_completed"] == "promote"


def test_lock_lost_does_not_advance_last_run_at(
    lethe_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A1 — lock_lost path uses clear_lock; last_run_at unchanged."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    pre = _consolidation_state_row(tenant_root)
    pre_last_run_at = None if pre is None else pre["last_run_at"]

    record: list[str] = []
    dispatch = _make_recording_dispatch(record=record)
    hb_call = 0

    def _spy(**_kwargs: Any) -> bool:
        nonlocal hb_call
        hb_call += 1
        return hb_call < 2  # True, False

    monkeypatch.setattr("lethe.runtime.consolidate.loop.heartbeat", _spy)
    result = _run_one_consolidate_with_dispatch(
        dispatch,
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
    )

    assert result.lock_lost is True
    state = _consolidation_state_row(tenant_root)
    assert state is not None
    assert state["last_run_at"] == pre_last_run_at


def test_lock_lost_mid_loop_preserves_committed_phase_writes(
    lethe_home: Path,
) -> None:
    """Gate 33 (A11): force_clear from another connection mid-loop preserves
    already-committed phase work (per-phase tx independence).

    Strategy: build a dispatch where phase 3 force-clears the lock (from
    another scheduler primitive) AFTER writing a marker S5 row. The
    heartbeat after phase 3 returns False (we lost the lock), aborting
    phases 4-6. The 3 marker rows from phases 1-3 must survive.
    """
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    from lethe.store.s5_log.writer import LogEntry, SqliteLogWriter

    writer = SqliteLogWriter(tenant_root)
    record: list[str] = []

    def make_marker_phase(name: str) -> Callable[[ConsolidateRun], PhaseResult]:
        def _phase(ctx: ConsolidateRun) -> PhaseResult:
            record.append(name)
            writer.append(
                LogEntry(
                    kind="phase_marker",
                    payload={"phase_name": name, "run_id": ctx.run_id},
                )
            )
            if name == "promote":
                # Simulate another scheduler stealing the lock mid-run
                force_clear_lock(tenant_id=TENANT, tenant_root=tenant_root)
            return _empty_phase_result()

        return _phase

    dispatch = tuple((name, make_marker_phase(name)) for name, _ in PHASE_DISPATCH)

    result = _run_one_consolidate_with_dispatch(
        dispatch,
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
    )

    assert result.lock_lost is True
    assert record == ["extract", "score", "promote"]
    # 3 marker rows survive (already-committed phase writes)
    markers = _s5_rows_of_kind(tenant_root, "phase_marker")
    assert len(markers) == 3
    assert [m["payload"]["phase_name"] for m in markers] == [
        "extract",
        "score",
        "promote",
    ]
    # 1 lock_lost row also recorded by the loop
    assert len(_s5_rows_of_kind(tenant_root, "lock_lost")) == 1
    # last_run_at NOT advanced (per A1)
    state = _consolidation_state_row(tenant_root)
    assert state is not None
    assert state["last_run_at"] is None


# ---------- (5) sink failure — mirror C6 A9 ---------- #


def test_sink_failure_collected_into_consolidate_run_result(lethe_home: Path) -> None:
    """Mirror IMPLEMENT 6 A9: sink raises → captured in sink_failures, NOT raised."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)

    def boom_sink(_env: Mapping[str, Any]) -> None:
        raise RuntimeError("sink offline")

    record: list[str] = []
    dispatch = _make_recording_dispatch(record=record)

    result = _run_one_consolidate_with_dispatch(
        dispatch,
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
        sink=boom_sink,
    )

    assert result.skipped is False
    assert result.error is None  # phases all "succeeded"; sink failure is non-fatal
    assert len(result.sink_failures) == 6
    for event_id, err_repr in result.sink_failures:
        assert isinstance(event_id, str) and len(event_id) == 36
        assert "RuntimeError" in err_repr and "sink offline" in err_repr
    # All 6 phases marked as succeeded (sink failure does NOT downgrade them)
    statuses = {pr.phase_name: pr.status for pr in result.phase_results}
    assert all(v == "succeeded" for v in statuses.values())


# ---------- (6) public surface has no test seam (A10) ---------- #


def test_run_one_consolidate_has_no_phase_dispatch_override_kwarg() -> None:
    """A10: public surface MUST NOT expose ``_phase_dispatch_override`` kwarg."""
    import inspect

    sig = inspect.signature(run_one_consolidate)
    assert "_phase_dispatch_override" not in sig.parameters
    assert "phase_dispatch_override" not in sig.parameters
    # Sanity: the private helper DOES accept dispatch as a positional arg
    private_sig = inspect.signature(_run_one_consolidate_with_dispatch)
    params = list(private_sig.parameters.values())
    assert params[0].name == "dispatch"


# ---------- (7) sanity — LoopPhaseResult / ConsolidateRunResult shape ---------- #


def test_consolidate_run_result_is_frozen_dataclass() -> None:
    """A7/A8 dataclasses are frozen — phases cannot mutate the result."""
    import dataclasses

    assert dataclasses.is_dataclass(ConsolidateRunResult)
    assert ConsolidateRunResult.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert dataclasses.is_dataclass(LoopPhaseResult)
    assert LoopPhaseResult.__dataclass_params__.frozen is True  # type: ignore[attr-defined]


# ---------- (8) gate elapsed: post-success run can re-acquire ---------- #


def test_second_run_after_gate_elapses_starts_fresh(lethe_home: Path) -> None:
    """After mark_success_and_release, gate eventually elapses + a new run acquires."""
    tenant_root, s1, s3, embedder = _bootstrap(lethe_home)
    base_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    record: list[str] = []
    first = _run_one_consolidate_with_dispatch(
        _make_recording_dispatch(record=record),
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
        now=base_now,
    )
    assert first.skipped is False
    after_gate = base_now + timedelta(seconds=GATE_INTERVAL_SECONDS + 1)
    second_record: list[str] = []
    second = _run_one_consolidate_with_dispatch(
        _make_recording_dispatch(record=second_record),
        tenant_id=TENANT,
        tenant_root=tenant_root,
        s1_client=s1,
        embedder=embedder,
        s3_client=s3,
        now=after_gate,
    )
    assert second.skipped is False
    assert second.run_id is not None
    assert second.run_id != first.run_id
