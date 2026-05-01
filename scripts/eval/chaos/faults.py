"""Chaos / fault injection — composition §7 failure modes (WS4 stub).

Contract
--------
Inject the named failure modes from `docs/03-composition-design.md` §7 and
assert "degrade, don't fail" pass criteria per row of that table. Plus the
two-stores-down matrix from §7.1.

Single failures (§7.1 of eval plan):
    s1_down, s2_down_or_locked, s3_stale, s3_unavailable,
    s4a_corrupted, s4b_diverged, s4b_regen_crash_mid_write,
    s5_append_fails, peer_message_corruption, dream_daemon_stuck,
    tenant_isolation_breach, schema_migration_mid_flight, disk_full,
    clock_skew_across_runtime_instances

Two-stores-down (§7.2 of eval plan):
    s1_and_s3, s2_and_s5, s1_and_s4

P0 short-circuits (§7.3): silent data corruption, cross-tenant exposure,
inconsistent health-endpoint state, alarm-should-fire-but-didn't.

Cross-refs
----------
- `docs/04-eval-plan.md` §7.
- `docs/03-composition-design.md` §7 + §7.1 (input contract).

Public surface (planned)
------------------------
    inject(failure_name: str, params: dict) -> ContextManager
        Context manager that injects the failure on enter, restores on exit.
    run_chaos_eval(modes: list[str]) -> dict
        Run the requested modes; return per-mode pass/fail dict.
    assert_no_p0(events: list[dict]) -> None
        Raises on any §7.3 event.
"""
from __future__ import annotations

import sys


def inject(failure_name: str, params: dict):
    """Context manager to inject a named failure. Wired but inert."""
    raise NotImplementedError(
        "chaos.faults.inject is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §7 and composition §7"
    )


def run_chaos_eval(modes: list) -> dict:
    """Run the requested chaos modes; return per-mode pass/fail."""
    raise NotImplementedError("chaos.faults.run_chaos_eval is a WS4 skeleton stub")


def assert_no_p0(events: list) -> None:
    """Raise on any §7.3 short-circuit event. Wired but inert."""
    raise NotImplementedError(
        "chaos.faults.assert_no_p0 is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §7.3"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.chaos.faults: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
