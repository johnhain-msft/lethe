"""Lethe-native eval-set Case schema (WS4 stub).

Contract
--------
Defines the common `Case` dataclass that every adapter (public benchmark or
Lethe-native) yields. The schema is the lingua franca of the harness; metric
modules consume `Case` objects and produce metric rows.

Cross-refs
----------
- `docs/04-eval-plan.md` §4 (Lethe-native eval set) — composition, source
  classes, contamination defenses, versioning.
- `docs/03-gaps/gap-14-eval-set-bias.md` §3 — taxonomy of source classes
  this schema must distinguish.
- `docs/03-gaps/gap-12-intent-classifier.md` §3 — the seven intent classes
  every Case is tagged with for classifier-F1 measurement.

Public surface (planned)
------------------------
    @dataclass(frozen=True)
    class Case:
        case_id: str
        version: int
        source: SourceClass               # operator | adversarial | ablation |
                                          # synthetic | author
        intent_class: IntentClass         # remember:fact | remember:preference |
                                          # remember:procedure | reply_only |
                                          # peer_route | drop | escalate
        provenance: Provenance            # origin record (tenant-id+opt-in for
                                          # operator, reviewer-id for adversarial,
                                          # ablation-spec, batch-id, author-id)
        contamination_protected: bool     # §4.4 — protected fact-ids never
                                          # write through `remember`
        tags: tuple[str, ...]             # free-form (e.g., synthetic_distrusted,
                                          # symmetric_pair_id, domain_class)
        payload: object                   # benchmark-specific case payload

    SourceClass: enum of {operator, adversarial, ablation, synthetic, author}
    IntentClass: enum of the seven gap-12 §3 classes
    Provenance: dataclass with origin-specific fields

Bias-resistance invariants enforced by the loader (`loader.py`):
    - operator share is 0% at v1.0 (no foreign-system ingest); §4.1, §4.6
    - author share ≤ 15% v1.0 / 10% v1.x; §4.1
    - adversarial share ≥ 30% v1.0; §4.1 floor
    - per-source positive:negative ratio ∈ [0.7, 1.3]; §4.3 symmetry policy
"""
from __future__ import annotations

import sys


def Case(*args, **kwargs):
    """Placeholder for the Case dataclass. Wired but inert.

    The real implementation will be a frozen dataclass; today it raises so
    that downstream code that tries to construct cases fails loudly.
    """
    raise NotImplementedError(
        "lethe_native.schema.Case is a WS4 skeleton stub; "
        "see docs/04-eval-plan.md §4 and gap-14 §3"
    )


if __name__ == "__main__":
    print(
        "scripts.eval.lethe_native.schema: not implemented (WS4 stub)",
        file=sys.stderr,
    )
    sys.exit(2)
