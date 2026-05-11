"""S4 — markdown surface (per-tenant filesystem layout).

Per composition §2 row 4 + §2.1, S4 is split into two sub-domains:

- **S4a** synthesis pages — markdown-canonical, authored, never auto-rewritten.
- **S4b** fact projections — graph-derived, regenerable from S1.

P1 scope: filesystem layout (``<storage_root>/<tenant_id>/{s4a,s4b}/``),
YAML frontmatter parse/serialize, deterministic stable-URI minting. No
qmd-class indexing; that lands with ``recall_synthesis`` in P3.
"""

from lethe.store.s4_md.frontmatter import (
    Frontmatter,
    dump,
    load,
    mint_uri,
)
from lethe.store.s4_md.layout import S4Layout

__all__ = ["Frontmatter", "S4Layout", "dump", "load", "mint_uri"]
