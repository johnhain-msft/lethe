"""S4 smoke: s4a/ + s4b/ created; frontmatter round-trips; URI minting deterministic."""

from __future__ import annotations

from pathlib import Path

import pytest

from lethe.store.s4_md import Frontmatter, S4Layout, dump, load, mint_uri


def test_s4_layout_creates_subdirs(tenant_root: Path) -> None:
    layout = S4Layout(tenant_root=tenant_root)
    assert not layout.is_ready()
    layout.create()
    assert layout.is_ready()
    assert layout.s4a_dir.is_dir()
    assert layout.s4b_dir.is_dir()


def test_s4_layout_create_is_idempotent(tenant_root: Path) -> None:
    layout = S4Layout(tenant_root=tenant_root)
    layout.create()
    layout.create()
    assert layout.is_ready()


def test_frontmatter_round_trip(tenant_root: Path) -> None:
    layout = S4Layout(tenant_root=tenant_root)
    layout.create()
    page = layout.s4a_dir / "preference-coffee.md"
    fm_in = Frontmatter(
        metadata={"kind": "preference", "title": "Coffee"},
        body="I prefer pour-over.\n",
    )
    dump(page, fm_in)

    fm_out = load(page)
    assert fm_out.metadata == {"kind": "preference", "title": "Coffee"}
    assert fm_out.body == "I prefer pour-over.\n"


def test_frontmatter_load_no_envelope_returns_body(tenant_root: Path) -> None:
    layout = S4Layout(tenant_root=tenant_root)
    layout.create()
    page = layout.s4a_dir / "plain.md"
    page.write_text("No frontmatter here.\n", encoding="utf-8")
    fm = load(page)
    assert fm.metadata == {}
    assert fm.body == "No frontmatter here.\n"


def test_mint_uri_is_deterministic(tenant_root: Path) -> None:
    layout = S4Layout(tenant_root=tenant_root)
    layout.create()
    page = layout.s4a_dir / "subdir" / "page.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.touch()
    uri_a = mint_uri("smoke", layout.s4a_dir, page)
    uri_b = mint_uri("smoke", layout.s4a_dir, page)
    assert uri_a == uri_b == "s4a://smoke/subdir/page.md"


def test_mint_uri_rejects_path_outside_s4a(tenant_root: Path) -> None:
    layout = S4Layout(tenant_root=tenant_root)
    layout.create()
    foreign = tenant_root / "s4b" / "projection.md"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.touch()
    with pytest.raises(ValueError):
        mint_uri("smoke", layout.s4a_dir, foreign)
