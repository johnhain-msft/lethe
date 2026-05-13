"""P2 audit lints — provenance enforcement (gap-05).

This package owns the two provenance lints listed in the P2 dev sub-plan
§3 row 5:

- :mod:`.provenance_required` — gap-05 §3.5 ``provenance-required`` lint:
  every S1 episode for the tenant must carry a non-empty ``source_uri``.
- :mod:`.provenance_resolvable` — gap-05 §6 ``provenance-resolvable``
  lint: every ``source_uri`` must either resolve to a real S4 artifact
  (``s4a:`` / ``s4b:`` schemes) **or** be a non-S4 scheme accepted under
  the tenant's ``provenance_drop_count`` policy in ``tenant_config``
  (per dev sub-plan §8 Q5; the counter lives in the existing
  ``tenant_config`` key-value row).

Two layers ship:

- **Workhorse** ``check_*`` functions (per-module) — take an explicit
  iterable of episode records + the open S2 connection. Tests inject the
  in-memory :class:`lethe.store.s1_graph._InMemoryGraphBackend` and call
  these directly.
- **Registry wrappers** registered into
  :data:`lethe.audit.integrity.REGISTRY` at import time. The wrappers
  satisfy :data:`lethe.audit.integrity.LintFn` (``Callable[[Path],
  list[str]]``). At P2 there is no production wiring that hands a live
  ``GraphitiBackend`` into the audit CLI, so the wrappers enumerate an
  empty episode set and return no findings on a freshly-bootstrapped
  tenant. P7 will plug the live graph backend through the same seam
  (sub-plan §8 Q1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lethe.audit.lints.provenance_required import (
    check_provenance_required,
    lint_provenance_required,
)
from lethe.audit.lints.provenance_resolvable import (
    check_provenance_resolvable,
    lint_provenance_resolvable,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from lethe.audit.integrity import LintRegistry

__all__ = [
    "check_provenance_required",
    "check_provenance_resolvable",
    "lint_provenance_required",
    "lint_provenance_resolvable",
    "register_p2_lints",
]


def register_p2_lints(registry: LintRegistry) -> None:
    """Register the two P2 provenance lints on ``registry``.

    Called by :mod:`lethe.audit.integrity` at module import time so the
    P2 lints are present whenever the CLI runs. Tests that monkey-patch
    a fresh registry into place can opt out by not re-invoking this.
    """
    registry.register("provenance-required", lint_provenance_required)
    registry.register("provenance-resolvable", lint_provenance_resolvable)
