"""Metrics emitter — writes report rows + renders headline tag (WS4 stub).

Contract
--------
Single sink for all metric rows. Writes per-run report directories under
`reports/<epoch>/<run-id>/` per `docs/04-eval-plan.md` §11.1, with files:

    summary.json
    per-phase/<phase>.json          (extract, score, promote, demote,
                                     consolidate, invalidate; §6)
    per-stratum/all-cases.json
    per-stratum/strict.json         (operator + adversarial + ablation +
                                     replay-only; §5.9)
    per-benchmark/longmemeval.json
    per-benchmark/locomo.json
    per-benchmark/dmr.json
    chaos.json                       (§7)
    shadow.json                      (only when shadow path active; §9)
    contamination.json               (§4.4)
    provenance.json                  (snapshot id + runtime + model versions)

Headline-tag rendering (mandatory; §2.1):
    v1.0 → "preliminary — operator slice empty (0%); author + adversarial +
            ablation + synthetic only; v1.x target 30% operator-derived"
    v1.x → no preliminary qualifier; both strata published.

CI gate: if `epoch == "v1.0"` and the headline tag is missing from a public
report, the build fails. Enforced by `render_headline_tag` returning
non-None for v1.0 unconditionally.

CI gate: if a public-benchmark report is emitted without an accompanying
cost row, the build fails (§3.4 invariant).

Cross-refs
----------
- `docs/04-eval-plan.md` §2.1, §5.9, §11.1, §11.2, §11.4.
- `docs/03-gaps/gap-14-eval-set-bias.md` §5(1) closing clause; §5(4).

Public surface (planned)
------------------------
    render_headline_tag(epoch: str, composition_stats: dict) -> str | None
    write_run_report(report_dir: pathlib.Path, payload: dict) -> None
    enforce_two_strata(payload: dict) -> None    # raises on §5.9 violation
    enforce_cost_with_accuracy(payload: dict) -> None  # raises on §3.4 violation
"""
from __future__ import annotations

import sys


def render_headline_tag(epoch: str, composition_stats: dict) -> str | None:
    """Render the mandatory headline tag for v1.0 reports.

    v1.0 returns the operator-slice-empty wording (§2.1). v1.x returns None
    once gating criterion satisfied. Wired but inert.
    """
    raise NotImplementedError(
        "metrics.emitter.render_headline_tag is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §2.1"
    )


def write_run_report(report_dir, payload: dict) -> None:
    """Write a complete per-run report tree. Wired but inert."""
    raise NotImplementedError(
        "metrics.emitter.write_run_report is a WS4 skeleton stub"
    )


def enforce_two_strata(payload: dict) -> None:
    """Raise if §5.9 two-strata reporting is violated. Wired but inert."""
    raise NotImplementedError(
        "metrics.emitter.enforce_two_strata is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §5.9"
    )


def enforce_cost_with_accuracy(payload: dict) -> None:
    """Raise if a public-benchmark accuracy is reported without cost (§3.4)."""
    raise NotImplementedError(
        "metrics.emitter.enforce_cost_with_accuracy is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §3.4"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.metrics.emitter: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
