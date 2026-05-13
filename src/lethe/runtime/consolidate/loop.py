"""Per-tenant consolidate loop — gate → lock → 6 phases → release (P4 C7).

Per IMPLEMENT 7 sub-plan §L.7 + §L.13: :func:`run_one_consolidate` is
THE single entry point that composes :mod:`.scheduler` primitives with
the canonical 6-phase :data:`.phases.PHASE_DISPATCH` tuple into one
consolidate cycle. Per A10: the dispatch-injectable test seam lives in
the private :func:`_run_one_consolidate_with_dispatch` helper; the
public :func:`run_one_consolidate` always uses
:data:`.phases.PHASE_DISPATCH` (no ``_phase_dispatch_override`` kwarg
on the public surface).

Cycle steps (A1 + A3 carry):

1. **PREFLIGHT** — :func:`.scheduler.should_run`. False → return
   :class:`ConsolidateRunResult` with ``skipped=True``,
   ``skip_reason="gate_not_elapsed"`` (per A7).
2. **ACQUIRE** — :func:`.scheduler.acquire_lock`.
   :class:`.scheduler.LockAcquisitionFailed` → return with
   ``skipped=True``, ``skip_reason="lock_held"``.
3. **GENERATE run_id** — random uuidv7 (per IMPLEMENT 6 A8).
4. **for each phase** (in canonical order):
   - try phase impl. On exception → log S5 ``kind='phase_failed'``,
     mark phase + remaining phases as ``status='failed'``/``'skipped'``
     in :class:`LoopPhaseResult`, set ``error``, break.
   - emit ``consolidate_phase`` envelope via :func:`.events.emit`
     (validates internally per emit's contract). Sink failures collect
     into ``ConsolidateRunResult.sink_failures`` (per IMPLEMENT 6 A9).
   - heartbeat **between phases only** (NOT after the final phase per
     A3) using fresh time per call (per A2). False return → log S5
     ``kind='lock_lost'``, mark remaining as ``'skipped'``, break.
5. **RELEASE** — per A1 split:
   - all 6 phases succeeded AND not lock_lost →
     :func:`.scheduler.mark_success_and_release` (advances
     ``last_run_at``).
   - any failure or lock_lost → :func:`.scheduler.clear_lock` (does
     NOT advance ``last_run_at`` so retry on next gate cycle).

Per A11 durability invariant: already-committed phase work survives
heartbeat loss (each phase's S2/S5 writes commit/rollback inside its
own tx, independent of the lock). The next consolidate cycle picks up
where this one left off (extract.py's cursor advance only commits if
its phase's tx committed).
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from lethe.runtime import events as _events_mod
from lethe.runtime.consolidate._reconciler import PhaseResult
from lethe.runtime.consolidate.embedder_protocol import Embedder
from lethe.runtime.consolidate.phases import (
    PHASE_DISPATCH,
    ConsolidateRun,
    PhaseImpl,
)
from lethe.runtime.consolidate.promote import (
    CONSOLIDATE_MODEL_VERSION,
    CONSOLIDATE_WEIGHTS_VERSION,
)
from lethe.runtime.consolidate.scheduler import (
    LockAcquisitionFailed,
    acquire_lock,
    clear_lock,
    heartbeat,
    mark_success_and_release,
    should_run,
)
from lethe.runtime.events import SinkCallable
from lethe.store.s1_graph.client import S1Client
from lethe.store.s3_vec.client import S3Client
from lethe.store.s5_log.writer import LogEntry, SqliteLogWriter


@dataclass(frozen=True)
class LoopPhaseResult:
    """Per-phase loop result with explicit status field (per IMPLEMENT 7 A8).

    - ``status="succeeded"`` — phase ran, returned :class:`PhaseResult`,
      no error. ``phase_result`` populated; ``error`` is None.
    - ``status="failed"`` — phase raised; ``phase_result`` is None;
      ``error`` carries ``"<ExceptionType>: <message>"``.
    - ``status="skipped"`` — phase did not run (an earlier phase failed
      or the lock was lost mid-cycle); ``phase_result`` is None;
      ``error`` is None.

    ``metrics`` is a forward-spec field for P9 fact-source telemetry
    (e.g. ``{"episodes_processed": N}`` for extract). At C7 it is
    always an empty mapping; phase adapters do not yet propagate
    metrics through the C6 :class:`PhaseResult` shape.
    """

    phase_name: str
    status: Literal["succeeded", "failed", "skipped"]
    phase_result: PhaseResult | None
    metrics: Mapping[str, int]
    error: str | None


@dataclass(frozen=True)
class ConsolidateRunResult:
    """Return value of :func:`run_one_consolidate` (per IMPLEMENT 7 A7).

    - ``skipped=True``: cycle did not run.
      - ``skip_reason="gate_not_elapsed"``: should_run() returned False.
      - ``skip_reason="lock_held"``: acquire_lock raised
        :class:`.scheduler.LockAcquisitionFailed`.
      - ``error`` is ``None`` on clean skip.
    - ``skipped=False``: cycle ran (lock acquired).
      - ``run_id`` populated.
      - ``phase_results`` has 6 entries (one per canonical phase) each
        with explicit ``status`` field (per A8).
      - ``lock_lost=True``: heartbeat returned False mid-cycle;
        remaining phases marked ``"skipped"``; lock cleared via
        :func:`.scheduler.clear_lock` (per A1).
      - ``error`` populated only for unexpected failures
        (``"<phase_name>:<error_repr>"``); ``None`` on happy path or
        on lock_lost (which is recoverable, not an error).
      - ``sink_failures``: per-event ``(event_id, error_repr)`` from
        the post-validate sink dispatch (mirror IMPLEMENT 6 A9).
    """

    skipped: bool
    skip_reason: Literal["gate_not_elapsed", "lock_held"] | None
    lock_acquired: bool
    run_id: str | None
    phase_results: tuple[LoopPhaseResult, ...]
    lock_lost: bool
    sink_failures: tuple[tuple[str, str], ...]
    error: str | None


def _generate_uuidv7(*, now: datetime) -> str:
    """Random uuidv7 for the per-run ``run_id`` (mirror api/recall.py + promote.py).

    Per IMPLEMENT 6 amendment A8: random (NOT deterministic). The
    duplicated copy mirrors :mod:`.promote` / :mod:`.demote` /
    :mod:`.invalidate` / :mod:`api.remember` / :mod:`api.recall`. A
    future P5+ shared util consolidates these copies (TODO).
    """
    unix_ts_ms = int(now.astimezone(UTC).timestamp() * 1000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    msb = (unix_ts_ms << 16) | (0x7 << 12) | rand_a
    lsb = (0b10 << 62) | rand_b
    value = (msb << 64) | lsb
    return str(uuid.UUID(int=value))


def _format_iso(dt: datetime) -> str:
    """RFC 3339 with Z suffix (per IMPLEMENT 6 amendment A11)."""
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _build_phase_envelope(
    *,
    tenant_id: str,
    phase_name: str,
    run_id: str,
    now: datetime,
) -> dict[str, Any]:
    """Build a ``consolidate_phase`` event envelope (events.py:155 contract)."""
    ts = _format_iso(now)
    return {
        "event_id": _generate_uuidv7(now=now),
        "event_type": "consolidate_phase",
        "tenant_id": tenant_id,
        "ts_recorded": ts,
        "ts_valid": ts,
        "model_version": CONSOLIDATE_MODEL_VERSION,
        "weights_version": CONSOLIDATE_WEIGHTS_VERSION,
        "contamination_protected": True,
        "phase_name": phase_name,
        "consolidate_run_id": run_id,
    }


def _emit_s5(*, tenant_root: Path, kind: str, payload: Mapping[str, Any]) -> None:
    """Append one S5 log entry via short-lived writer.

    Loop S5 writes (``phase_failed``, ``lock_lost``) are post-event,
    not inside any phase's tx, so the short-lived
    :func:`SqliteLogWriter.append` is appropriate (NOT
    ``append_with_conn`` which is for the C6 cross-store T2 case).
    """
    writer = SqliteLogWriter(tenant_root)
    writer.append(LogEntry(kind=kind, payload=dict(payload)))


def _run_one_consolidate_with_dispatch(
    dispatch: Sequence[tuple[str, PhaseImpl]],
    *,
    tenant_id: str,
    tenant_root: Path,
    s1_client: S1Client,
    embedder: Embedder,
    s3_client: S3Client,
    sink: SinkCallable | None = None,
    now: datetime | None = None,
) -> ConsolidateRunResult:
    """Private dispatch-injectable orchestrator (per IMPLEMENT 7 A10).

    Tests inject a recording dispatch to assert canonical order +
    failure/lock-lost behavior without invoking real C5/C6 phase
    bodies. Public callers go through :func:`run_one_consolidate`,
    which always uses :data:`.phases.PHASE_DISPATCH`.
    """
    n = now if now is not None else datetime.now(UTC)

    # Step 1: PREFLIGHT gate check (cheap hint per §L.2 + B-2)
    if not should_run(tenant_id=tenant_id, tenant_root=tenant_root, now=n):
        return ConsolidateRunResult(
            skipped=True,
            skip_reason="gate_not_elapsed",
            lock_acquired=False,
            run_id=None,
            phase_results=(),
            lock_lost=False,
            sink_failures=(),
            error=None,
        )

    # Step 2: ACQUIRE LOCK (TOCTOU-tolerant per B-2 — acquire is the
    # AUTHORITATIVE atomic gate; should_run is just a hint)
    try:
        lock_token = acquire_lock(
            tenant_id=tenant_id,
            tenant_root=tenant_root,
            now=n,
        )
    except LockAcquisitionFailed:
        return ConsolidateRunResult(
            skipped=True,
            skip_reason="lock_held",
            lock_acquired=False,
            run_id=None,
            phase_results=(),
            lock_lost=False,
            sink_failures=(),
            error=None,
        )

    # Step 3: GENERATE run_id (random uuidv7 per IMPLEMENT 6 A8)
    run_id = _generate_uuidv7(now=n)

    # Step 4: build context + iterate dispatch
    ctx = ConsolidateRun(
        tenant_id=tenant_id,
        tenant_root=tenant_root,
        s1_client=s1_client,
        embedder=embedder,
        s3_client=s3_client,
        run_id=run_id,
        sink=sink,
        now=n,
    )

    phase_results: list[LoopPhaseResult] = []
    sink_failures: list[tuple[str, str]] = []
    lock_lost = False
    error: str | None = None

    dispatch_seq: list[tuple[str, PhaseImpl]] = list(dispatch)
    last_index = len(dispatch_seq) - 1

    for index, (phase_name, phase_impl) in enumerate(dispatch_seq):
        # Run the phase
        try:
            phase_result = phase_impl(ctx)
        except Exception as phase_err:  # noqa: BLE001 — phase exceptions intentionally caught broad
            error_repr = f"{type(phase_err).__name__}: {phase_err}"
            phase_results.append(
                LoopPhaseResult(
                    phase_name=phase_name,
                    status="failed",
                    phase_result=None,
                    metrics={},
                    error=error_repr,
                )
            )
            error = f"{phase_name}:{error_repr}"
            _emit_s5(
                tenant_root=tenant_root,
                kind="phase_failed",
                payload={
                    "tenant_id": tenant_id,
                    "run_id": run_id,
                    "phase_name": phase_name,
                    "error": error_repr,
                    "now": _format_iso(n),
                },
            )
            for skipped_name, _ in dispatch_seq[index + 1 :]:
                phase_results.append(
                    LoopPhaseResult(
                        phase_name=skipped_name,
                        status="skipped",
                        phase_result=None,
                        metrics={},
                        error=None,
                    )
                )
            break

        # Emit consolidate_phase envelope (validates internally via
        # events.emit → events.validate per gate 16). Sink failures
        # collect (mirror IMPLEMENT 6 A9 sink-failure semantics).
        envelope = _build_phase_envelope(
            tenant_id=tenant_id,
            phase_name=phase_name,
            run_id=run_id,
            now=n,
        )
        try:
            _events_mod.emit(envelope, sink=sink)
        except Exception as sink_err:  # noqa: BLE001 — sink errors are best-effort per A9
            sink_failures.append(
                (
                    str(envelope["event_id"]),
                    f"{type(sink_err).__name__}: {sink_err}",
                )
            )

        phase_results.append(
            LoopPhaseResult(
                phase_name=phase_name,
                status="succeeded",
                phase_result=phase_result,
                metrics={},
                error=None,
            )
        )

        # Step 4b: heartbeat ONLY between phases (per A3 — NOT after
        # the final phase). Per A2: pass no ``now`` so heartbeat
        # captures fresh time.
        if index < last_index and not heartbeat(
            tenant_id=tenant_id,
            tenant_root=tenant_root,
            lock_token=lock_token,
        ):
            lock_lost = True
            _emit_s5(
                tenant_root=tenant_root,
                kind="lock_lost",
                payload={
                    "tenant_id": tenant_id,
                    "run_id": run_id,
                    "lock_token": lock_token,
                    "phase_completed": phase_name,
                    "now": _format_iso(n),
                },
            )
            for skipped_name, _ in dispatch_seq[index + 1 :]:
                phase_results.append(
                    LoopPhaseResult(
                        phase_name=skipped_name,
                        status="skipped",
                        phase_result=None,
                        metrics={},
                        error=None,
                    )
                )
            break

    # Step 5: RELEASE per A1 — split based on outcome
    all_succeeded = all(pr.status == "succeeded" for pr in phase_results)
    if all_succeeded and not lock_lost:
        mark_success_and_release(
            tenant_id=tenant_id,
            tenant_root=tenant_root,
            lock_token=lock_token,
            now=n,
        )
    else:
        clear_lock(
            tenant_id=tenant_id,
            tenant_root=tenant_root,
            lock_token=lock_token,
            now=n,
        )

    return ConsolidateRunResult(
        skipped=False,
        skip_reason=None,
        lock_acquired=True,
        run_id=run_id,
        phase_results=tuple(phase_results),
        lock_lost=lock_lost,
        sink_failures=tuple(sink_failures),
        error=error,
    )


def run_one_consolidate(
    *,
    tenant_id: str,
    tenant_root: Path,
    s1_client: S1Client,
    embedder: Embedder,
    s3_client: S3Client,
    sink: SinkCallable | None = None,
    now: datetime | None = None,
) -> ConsolidateRunResult:
    """Run one consolidate cycle for ``tenant_id`` — the public entry point.

    Composes :mod:`.scheduler` primitives with
    :data:`.phases.PHASE_DISPATCH` per IMPLEMENT 7 §L.7. Per A10 the
    public surface has NO test seam — tests call the private
    :func:`_run_one_consolidate_with_dispatch` directly with an
    injected dispatch sequence to assert canonical order + failure
    behavior without invoking the real C5/C6 phase bodies.
    """
    return _run_one_consolidate_with_dispatch(
        PHASE_DISPATCH,
        tenant_id=tenant_id,
        tenant_root=tenant_root,
        s1_client=s1_client,
        embedder=embedder,
        s3_client=s3_client,
        sink=sink,
        now=now,
    )
