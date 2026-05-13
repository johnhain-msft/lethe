"""Audit smoke: lethe-audit lint --integrity returns clean on empty tenant.

Per docs/IMPLEMENTATION.md §2.1 exit gate #2.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lethe.audit import LintRegistry, LintResult, lint_integrity, main
from lethe.audit.integrity import REGISTRY


def test_lint_integrity_clean_on_empty_tenant(lethe_home: Path) -> None:
    result = lint_integrity(tenant_id="smoke-tenant", storage_root=lethe_home)
    assert isinstance(result, LintResult)
    assert result.status == "clean"
    assert result.findings == ()
    assert result.tenant_id == "smoke-tenant"


def test_main_clean_exits_zero(
    lethe_home: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        [
            "lint",
            "--integrity",
            "--tenant-id",
            "smoke-tenant",
            "--storage-root",
            str(lethe_home),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert "status=clean" in captured.out
    assert "tenant=smoke-tenant" in captured.out


def test_main_dirty_exits_one(
    lethe_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirms exit-code branching: a registered failing lint flips status."""
    fake = LintRegistry()
    fake.register("smoke-failing-lint", lambda _root: ["fabricated finding"])
    monkeypatch.setattr("lethe.audit.integrity.REGISTRY", fake)
    rc = main(
        [
            "lint",
            "--integrity",
            "--tenant-id",
            "smoke-tenant",
            "--storage-root",
            str(lethe_home),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "status=dirty" in captured.out
    assert "smoke-failing-lint" in captured.out


def test_registry_has_p2_provenance_lints() -> None:
    """P2 commit-5 invariant: provenance lints are registered."""
    names = REGISTRY.names()
    assert "provenance-required" in names
    assert "provenance-resolvable" in names


def test_lint_integrity_rejects_empty_tenant_id(lethe_home: Path) -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        lint_integrity(tenant_id="", storage_root=lethe_home)
