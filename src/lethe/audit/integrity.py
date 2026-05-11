"""Integrity lint registry + ``lethe-audit`` CLI entry-point.

Per ``docs/03-gaps/gap-08-crash-safety.md`` §3.5, the startup integrity
check runs on Lethe runtime boot and:

- recovers S2 WAL,
- reconciles orphaned T1/T2 (episode-without-ledger or vice versa),
- reconciles S5 vs S1 state per gap-13 detection signals.

P1 ships the **registry seam** only. The registry is empty; concrete lints
land alongside the verbs that produce the state they audit (P2/P5/P8 per
the IMPL §3 risk register R2/R3). On an empty tenant with no lints, the
contract is trivially satisfied: status ``clean``, exit ``0``.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from lethe.runtime import bootstrap

LintFn = Callable[[Path], list[str]]
"""A lint callable: takes the tenant root, returns a list of finding strings."""


@dataclass(frozen=True)
class LintResult:
    """Aggregated lint outcome for one ``lint --integrity`` run."""

    tenant_id: str
    findings: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        return "clean" if not self.findings else "dirty"


@dataclass
class LintRegistry:
    """Mutable registry of lints. Empty at P1; populated by P2/P5/P8."""

    _lints: list[tuple[str, LintFn]] = field(default_factory=list)

    def register(self, name: str, fn: LintFn) -> None:
        self._lints.append((name, fn))

    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self._lints)

    def run(self, tenant_root: Path) -> list[str]:
        findings: list[str] = []
        for name, fn in self._lints:
            for msg in fn(tenant_root):
                findings.append(f"[{name}] {msg}")
        return findings


# Module-level registry. Concrete lints add themselves at import time as their
# owning packages are wired in later phases.
REGISTRY = LintRegistry()


def _lethe_home() -> Path:
    home_env = os.environ.get("LETHE_HOME")
    if home_env:
        return Path(home_env)
    return Path.home() / ".lethe"


def lint_integrity(tenant_id: str, storage_root: Path | None = None) -> LintResult:
    """Run all registered lints against ``<storage_root>/tenants/<tenant_id>/``.

    On a missing tenant root, the function bootstraps it first — this matches
    the gap-08 §3.5 startup posture (the integrity check is part of the
    boot sequence; a fresh tenant must come up clean).
    """
    if not tenant_id:
        raise ValueError("tenant_id must be a non-empty string")
    root = storage_root if storage_root is not None else _lethe_home()
    bootstrap(tenant_id=tenant_id, storage_root=root)
    tenant_root = root / "tenants" / tenant_id
    findings = REGISTRY.run(tenant_root)
    return LintResult(tenant_id=tenant_id, findings=tuple(findings))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lethe-audit",
        description="Lethe audit/lint CLI (gap-08 §3.5 integrity check).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    lint = sub.add_parser("lint", help="Run lint checks against a tenant.")
    lint.add_argument(
        "--integrity",
        action="store_true",
        help="Run the integrity lint suite (gap-08 §3.5).",
    )
    lint.add_argument(
        "--tenant-id",
        required=True,
        help="Tenant identifier to audit.",
    )
    lint.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="Storage root override (defaults to $LETHE_HOME or ~/.lethe).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry-point. Returns process exit code (0 on success)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "lint":
        if not args.integrity:
            print("error: lint subcommand requires --integrity at P1", file=sys.stderr)
            return 2
        result = lint_integrity(
            tenant_id=args.tenant_id,
            storage_root=args.storage_root,
        )
        print(f"status={result.status} tenant={result.tenant_id}")
        for finding in result.findings:
            print(f"  - {finding}")
        return 0 if result.status == "clean" else 1

    parser.error(f"unknown command: {args.command}")
    return 2  # unreachable; argparse exits before this


if __name__ == "__main__":  # pragma: no cover - exercised via console_script
    raise SystemExit(main())
