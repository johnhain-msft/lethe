"""Tenant-init bootstrap (composition §3.5).

Empty storage root in → all five stores present, ready to serve. The
preferences-prepend path (composition §3.5) returns ``[]`` at P1 because
the qmd-class index over S4a doesn't land until P3 (recall_synthesis).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lethe.store.s1_graph import S1Client, _InMemoryGraphBackend
from lethe.store.s2_meta import S2Schema
from lethe.store.s3_vec import S3Client
from lethe.store.s4_md import S4Layout


@dataclass(frozen=True)
class TenantBootstrap:
    """Result of :func:`bootstrap`. All five flags are ``True`` on success."""

    tenant_id: str
    storage_root: Path
    s1_ready: bool
    s2_ready: bool
    s3_ready: bool
    s4_ready: bool
    s5_ready: bool

    @property
    def all_ready(self) -> bool:
        return (
            self.s1_ready
            and self.s2_ready
            and self.s3_ready
            and self.s4_ready
            and self.s5_ready
        )


def _tenant_root(storage_root: Path, tenant_id: str) -> Path:
    return storage_root / "tenants" / tenant_id


def bootstrap(tenant_id: str, storage_root: Path) -> TenantBootstrap:
    """Create empty stores under ``storage_root/tenants/<tenant_id>/``.

    Idempotent: re-invocation against an already-bootstrapped root succeeds
    and returns the same ready-flags.

    P1 uses the in-memory S1 backend per plan.md §B1; the production
    Graphiti backend wires in at P2 once the write path actually needs to
    talk to Neo4j/FalkorDB.
    """
    if not tenant_id:
        raise ValueError("tenant_id must be a non-empty string")

    tenant_root = _tenant_root(storage_root, tenant_id)
    tenant_root.mkdir(parents=True, exist_ok=True)

    # S1: in-memory backend at P1 (composition §5.2 group_id partition).
    s1 = S1Client(_InMemoryGraphBackend(), tenant_id=tenant_id)
    s1.bootstrap()
    s1_ready = s1.is_ready()

    # S2: per-tenant SQLite file with WAL pragmas.
    s2_conn = S2Schema(tenant_root=tenant_root).create()
    s2_conn.close()
    s2_ready = True

    # S3: per-tenant SQLite file + sqlite-vec.
    s3 = S3Client(tenant_root=tenant_root)
    s3.bootstrap()
    s3.close()
    s3_ready = True

    # S4: per-tenant filesystem layout (s4a/ + s4b/).
    layout = S4Layout(tenant_root=tenant_root)
    layout.create()
    s4_ready = layout.is_ready()

    # S5: lives inside S2 (facilitator §(g) lock). The s5_consolidation_log
    # table was already created by S2Schema.create() above; mark ready.
    s5_ready = True

    return TenantBootstrap(
        tenant_id=tenant_id,
        storage_root=storage_root,
        s1_ready=s1_ready,
        s2_ready=s2_ready,
        s3_ready=s3_ready,
        s4_ready=s4_ready,
        s5_ready=s5_ready,
    )
