"""CP-I02 isolated drill v2. Synthetic data, temp dirs, spare port; no deploy, no real service.

usage: python drill2.py <repo> <old-rev> <out.json>
Old release = <old-rev> checked out in a temp git worktree. New release = the repo HEAD source.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from siro.core.releases import ReleaseManager, ReleaseManifest
from siro.persistence.sqlite import SQLiteStore, load_migrations

HERE = Path(__file__).resolve().parent
KEY = b"drill-key-not-a-secret"
REPO, OLD_REV, OUT = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
out: dict[str, object] = {"old_rev": OLD_REV, "steps": []}
PY = sys.executable


def step(name: str, **v: object) -> None:
    out["steps"].append({"step": name, **v})  # type: ignore[union-attr]
    print(name, v, flush=True)


def git(*args: str) -> str:
    done = subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True, text=True)
    return done.stdout.strip()


def old_python(worktree: Path, code: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(worktree / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([PY, "-c", code, *args], env=env, cwd=worktree, capture_output=True, text=True, timeout=120)


def manifest(m: ReleaseManager, b: Path, ver: str, lo: int, hi: int) -> ReleaseManifest:
    a = ReleaseManifest(version=ver, source_sha256=m._digest_v2(b), signature="0" * 64,
                        min_schema=lo, max_schema=hi, signing_format="siro-release-manifest-v2")
    return a.model_copy(update={"signature": hmac.new(KEY, a.signing_payload(), hashlib.sha256).hexdigest()})


def schema_of(db: Path) -> int:
    with sqlite3.connect(db) as c:
        return int(c.execute("SELECT count(*) FROM schema_migrations").fetchone()[0])


def columns(db: Path) -> dict[str, list[str]]:
    query = (
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "AND name!='schema_migrations' ORDER BY name"
    )
    with sqlite3.connect(db) as c:
        names = [n for (n,) in c.execute(query)]
        return {n: [r[1] for r in c.execute(f'PRAGMA table_info("{n}")')] for n in names}


def digest(db: Path, base: dict[str, list[str]]) -> str:
    """Hash of the rows of every table (and column) that existed at the old schema."""
    with sqlite3.connect(db) as c:
        rows = []
        for t, cols in base.items():
            sel = ", ".join(f'"{x}"' for x in cols)
            rows.append((t, c.execute(f'SELECT {sel} FROM "{t}" ORDER BY {sel}').fetchall()))
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def hc(report: Path, db: Path) -> tuple[str, ...]:
    os.environ["SIRO_DRILL_HC_DB"], os.environ["SIRO_DRILL_HC_REPORT"] = str(db), str(report)
    return (PY, str(HERE / "hc.py"))


def read_report(p: Path) -> dict[str, object]:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


OLD_INIT = (
    "import asyncio,sys;from pathlib import Path;from siro.persistence.sqlite import SQLiteStore;"
    "asyncio.run(SQLiteStore(Path(sys.argv[1])).initialize())"
)
OLD_PROBE = """
import asyncio, sqlite3, sys
from pathlib import Path
from siro.persistence.sqlite import SQLiteStore
p = Path(sys.argv[1]); asyncio.run(SQLiteStore(p).initialize())
c = sqlite3.connect(p)
print(c.execute('pragma integrity_check').fetchone()[0], c.execute('select count(*) from drill_notes').fetchone()[0],
      c.execute('select count(*) from schema_migrations').fetchone()[0])
"""

with tempfile.TemporaryDirectory() as td:
    t = Path(td)
    wt = t / "old-wt"
    git("worktree", "add", "--detach", str(wt), OLD_REV)
    try:
        out["old_sha"] = git("rev-parse", OLD_REV)
        out["new_sha"] = git("rev-parse", "HEAD")
        old_n = len(list((wt / "src/siro/persistence/migrations").glob("*.sql")))
        new_n = len(load_migrations())
        step("versions", old_migrations=old_n, new_migrations=new_n)

        def bundle(src: Path, name: str) -> Path:
            dest = t / name
            shutil.copytree(src / "src" / "siro", dest / "src" / "siro", ignore=shutil.ignore_patterns("__pycache__"))
            return dest

        b_old = bundle(wt, "b_old")
        data = subprocess.run(["git", "-C", str(REPO), "archive", "HEAD", "src/siro"], check=True, capture_output=True).stdout
        b_new = t / "b_new"
        b_new.mkdir()
        tarfile.open(fileobj=io.BytesIO(data)).extractall(b_new, filter="data")

        # 1. Database made by the OLD code (schema = old_n) plus synthetic rows.
        db = t / "data" / "siro.db"
        r = old_python(wt, OLD_INIT, str(db))
        assert r.returncode == 0, r.stderr[-800:]
        with sqlite3.connect(db) as c:
            c.execute("CREATE TABLE drill_notes(id INTEGER PRIMARY KEY, body TEXT)")
            c.executemany("INSERT INTO drill_notes(body) VALUES (?)", [(f"synthetic-{i}",) for i in range(50)])
        base = columns(db)
        h_pre = digest(db, base)
        step("old_db", schema=schema_of(db), tables=len(base), data_hash=h_pre)

        # 2. Old era: a manager that only knows the old schema activates the old release (honest manifest).
        era_old = ReleaseManager(t / "mgr", KEY, current_schema=old_n, database=db)
        r1 = era_old.stage_and_activate(b_old, manifest(era_old, b_old, "1.0.0", 1, old_n), hc(t / "hc_old.json", db))
        step("activate_old_era", status=r1.status, active=era_old.active_version(), healthcheck=read_report(t / "hc_old.json"))

        # 3. Deploy new: the pre-deploy backup is taken by stage_and_activate, then the new code migrates the DB.
        m = ReleaseManager(t / "mgr", KEY, current_schema=new_n, database=db)
        r2 = m.stage_and_activate(b_new, manifest(m, b_new, "1.1.0", 1, new_n), hc(t / "hc_new.json", db))
        step("deploy_new", status=r2.status, active=m.active_version(), healthcheck=read_report(t / "hc_new.json"))
        asyncio.run(SQLiteStore(db).initialize())
        with sqlite3.connect(db) as c:
            c.executemany("INSERT INTO drill_notes(body) VALUES (?)", [(f"post-deploy-{i}",) for i in range(5)])
        step("migrated", schema=schema_of(db))
        backup = t / "mgr" / "backups" / "before-1.1.0.sqlite3"
        step("pre_deploy_backup", exists=backup.is_file(), schema=schema_of(backup) if backup.is_file() else None)

        # 4. Item 1: can the old CODE read the new-schema database?
        db_new_copy = t / "copy_new" / "siro.db"
        db_new_copy.parent.mkdir()
        with sqlite3.connect(db) as s, sqlite3.connect(db_new_copy) as d:
            s.backup(d)
        probe = old_python(wt, OLD_PROBE, str(db_new_copy))
        step("old_code_opens_new_schema_db", returncode=probe.returncode, stdout=probe.stdout.strip(), stderr=probe.stderr.strip()[-400:])
        rep = t / "hc_old_on_new.json"
        rc = subprocess.run(hc(rep, db_new_copy), cwd=b_old, capture_output=True, timeout=90).returncode
        step("old_gateway_on_new_schema_db", healthcheck_exit=rc, report=read_report(rep))

        # 5. Rollback with the new schema in place: the release gate must refuse.
        r3 = m.rollback()
        step("rollback_on_new_schema", status=r3.status, active=m.active_version())

        # 6. The rollback path that works: restore the pre-deploy backup (service stopped), then flip release.
        # The new code's restore re-applies migrations, so it ends at the new schema again: not a rollback.
        asyncio.run(SQLiteStore(db).restore_from(backup))
        step("restore_with_new_code", schema=schema_of(db), data_hash_same=digest(db, base) == h_pre)
        r3b = m.rollback()
        step("rollback_after_new_code_restore", status=r3b.status, active=m.active_version())
        # The old release restores its own backup, which keeps the old schema.
        restore_old = "import asyncio,sys;from pathlib import Path;from siro.persistence.sqlite import SQLiteStore;asyncio.run(SQLiteStore(Path(sys.argv[1])).restore_from(Path(sys.argv[2])))"
        rr = old_python(wt, restore_old, str(db), str(backup))
        assert rr.returncode == 0, rr.stderr[-800:]
        with sqlite3.connect(db) as c:
            left = c.execute("select count(*) from drill_notes where body like 'post-deploy-%'").fetchone()[0]
        step("restore_with_old_code", schema=schema_of(db), data_hash_same=digest(db, base) == h_pre, post_deploy_rows_left=left)
        r4 = m.rollback()
        step("rollback_after_restore", status=r4.status, active=m.active_version(), data_hash_same=digest(db, base) == h_pre)
        rep2 = t / "hc_old_after_rollback.json"
        rc2 = subprocess.run(hc(rep2, db), cwd=t / "mgr" / "releases" / "1.0.0", capture_output=True, timeout=90).returncode
        step("old_gateway_after_rollback", healthcheck_exit=rc2, report=read_report(rep2))

        # 7. Re-apply the new release; data written before the deploy must survive the migration.
        r5 = m.stage_and_activate(b_new, manifest(m, b_new, "1.1.1", 1, new_n), hc(t / "hc_reapply.json", db))
        step("reapply", status=r5.status, active=m.active_version(), healthcheck=read_report(t / "hc_reapply.json"))
        asyncio.run(SQLiteStore(db).initialize())
        step("reapply_migrated", schema=schema_of(db), data_hash_same=digest(db, base) == h_pre)

        # 8. A failing healthcheck keeps the active release.
        bad = m.stage_and_activate(b_new, manifest(m, b_new, "1.1.2", 1, new_n), (PY, "-c", "raise SystemExit(1)"))
        step("failed_healthcheck_keeps_active", status=bad.status, active=m.active_version())
    finally:
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(wt)], capture_output=True)
        subprocess.run(["git", "-C", str(REPO), "worktree", "prune"], capture_output=True)
checks = [s for s in out["steps"] if "data_hash_same" in s]  # type: ignore[union-attr]
out["data_hashes_match"] = all(s["data_hash_same"] for s in checks)
OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
print("data_hashes_match", out["data_hashes_match"])
