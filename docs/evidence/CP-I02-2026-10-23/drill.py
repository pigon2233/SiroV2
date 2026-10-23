"""CP-I02 isolated rollback -> reapply drill. Synthetic data, temp dirs only; no deploy."""
from __future__ import annotations

import hashlib, hmac, io, json, sqlite3, subprocess, sys, tarfile, tempfile
from pathlib import Path

from siro.core.releases import ReleaseManager, ReleaseManifest
from siro.persistence.sqlite import SQLiteStore, load_migrations

KEY = b"drill-key-not-a-secret"
REPO = Path(sys.argv[1])
OLD, NEW = sys.argv[2], sys.argv[3]
out: dict[str, object] = {"old": OLD, "new": NEW, "steps": []}


def step(name: str, **v: object) -> None:
    out["steps"].append({"step": name, **v})  # type: ignore[union-attr]
    print(name, v)


def bundle(rev: str, dest: Path) -> None:
    data = subprocess.run(["git", "-C", str(REPO), "archive", rev, "src/siro"], check=True, capture_output=True).stdout
    dest.mkdir(parents=True)
    tarfile.open(fileobj=io.BytesIO(data)).extractall(dest, filter="data")


def manifest(m: ReleaseManager, b: Path, ver: str, schema: int) -> ReleaseManifest:
    a = ReleaseManifest(version=ver, source_sha256=m._digest_v2(b), signature="0" * 64,
                        min_schema=1, max_schema=schema, signing_format="siro-release-manifest-v2")
    return a.model_copy(update={"signature": hmac.new(KEY, a.signing_payload(), hashlib.sha256).hexdigest()})


def dump(db: Path) -> str:
    with sqlite3.connect(db) as c:
        rows = [(t, c.execute(f"SELECT * FROM {t} ORDER BY 1,2").fetchall()) for (t,) in
                c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return hashlib.sha256(repr(rows).encode()).hexdigest()


with tempfile.TemporaryDirectory() as td:
    t = Path(td)
    db = t / "data.sqlite3"
    n = len(load_migrations())
    import asyncio
    store = SQLiteStore(db)
    asyncio.run(store.initialize())
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE IF NOT EXISTS drill_notes(id INTEGER PRIMARY KEY, body TEXT)")
        c.executemany("INSERT INTO drill_notes(body) VALUES (?)", [(f"synthetic-{i}",) for i in range(50)])
        schema = c.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    step("init", migrations=n, schema=schema, data_hash=dump(db))
    h0 = dump(db)

    m = ReleaseManager(t / "mgr", KEY, current_schema=schema, database=db)
    b_old, b_new = t / "b_old", t / "b_new"
    bundle(OLD, b_old); bundle(NEW, b_new)
    ok = (sys.executable, "-c", "pass")
    r = m.stage_and_activate(b_old, manifest(m, b_old, "1.0.0", schema), ok)
    step("activate_old", status=r.status, active=m.active_version())
    r = m.stage_and_activate(b_new, manifest(m, b_new, "1.1.0", schema), ok)
    step("activate_new", status=r.status, active=m.active_version(), data_hash_same=dump(db) == h0)
    r = m.rollback()
    step("rollback", status=r.status, active=m.active_version(), data_hash_same=dump(db) == h0)
    # reapply: version dir already exists, so bump patch with identical source
    r = m.stage_and_activate(b_new, manifest(m, b_new, "1.1.1", schema), ok)
    step("reapply", status=r.status, active=m.active_version(), data_hash_same=dump(db) == h0)
    bad = m.stage_and_activate(b_new, manifest(m, b_new, "1.1.2", schema), (sys.executable, "-c", "raise SystemExit(1)"))
    step("failed_healthcheck_keeps_active", status=bad.status, active=m.active_version())
    # backup -> restore into empty dir
    restored = t / "restored.sqlite3"
    asyncio.run(store.backup_to(t / "backup.sqlite3"))
    other = SQLiteStore(restored)
    asyncio.run(other.initialize())
    asyncio.run(other.restore_from(t / "backup.sqlite3"))
    step("backup_restore", restored_hash_same=dump(restored) == h0)
    out["pass"] = all(s.get("data_hash_same", True) and s.get("restored_hash_same", True) for s in out["steps"])  # type: ignore[union-attr]
Path(sys.argv[4]).write_text(json.dumps(out, indent=2), encoding="utf-8")
