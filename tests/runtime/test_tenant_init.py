"""Runtime smoke: tenant-init end-to-end + preferences-prepend stub."""

from __future__ import annotations

from pathlib import Path

import pytest

from lethe.runtime import TenantBootstrap, bootstrap, preferences_prepend


def test_bootstrap_empty_root_yields_all_stores_ready(lethe_home: Path) -> None:
    result = bootstrap(tenant_id="smoke-tenant", storage_root=lethe_home)
    assert isinstance(result, TenantBootstrap)
    assert result.tenant_id == "smoke-tenant"
    assert result.all_ready
    assert result.s1_ready
    assert result.s2_ready
    assert result.s3_ready
    assert result.s4_ready
    assert result.s5_ready


def test_bootstrap_creates_expected_layout(lethe_home: Path) -> None:
    bootstrap(tenant_id="smoke-tenant", storage_root=lethe_home)
    tenant_root = lethe_home / "tenants" / "smoke-tenant"
    assert tenant_root.is_dir()
    assert (tenant_root / "s2_meta.sqlite").is_file()
    assert (tenant_root / "s3_vec.sqlite").is_file()
    assert (tenant_root / "s4a").is_dir()
    assert (tenant_root / "s4b").is_dir()


def test_bootstrap_is_idempotent(lethe_home: Path) -> None:
    a = bootstrap(tenant_id="smoke-tenant", storage_root=lethe_home)
    b = bootstrap(tenant_id="smoke-tenant", storage_root=lethe_home)
    assert a.all_ready and b.all_ready


def test_preferences_prepend_returns_empty_on_fresh_tenant(lethe_home: Path) -> None:
    bootstrap(tenant_id="smoke-tenant", storage_root=lethe_home)
    assert preferences_prepend("smoke-tenant", lethe_home) == []


def test_bootstrap_rejects_empty_tenant_id(lethe_home: Path) -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        bootstrap(tenant_id="", storage_root=lethe_home)


def test_preferences_prepend_rejects_empty_tenant_id(lethe_home: Path) -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        preferences_prepend("", lethe_home)
