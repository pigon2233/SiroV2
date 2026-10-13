from __future__ import annotations

# Actual current-source repeated cancellation + primary-error observability probe.
# The archived current-probe.json is the 9b4da... pre-wait-repair observation.
# Re-running this file reads current source and writes only a /tmp result, leaving
# both archived before-probe results untouched. Fixtures contain synthetic data.

import asyncio
import hashlib
import json
import sqlite3
import sys
import tempfile
import threading
from contextlib import closing
from pathlib import Path

from siro.persistence import sqlite as module
from siro.persistence.sqlite import SQLiteStore, MigrationError, apply_migrations, load_migrations

async def event_wait(event):
    async with asyncio.timeout(3):
        while not event.is_set():
            await asyncio.sleep(.002)

async def run():
    loop = asyncio.get_running_loop()
    handler = loop.get_exception_handler()
    messages = []
    loop.set_exception_handler(lambda loop, ctx: messages.append({
        'message': str(ctx.get('message')),
        'exception_type': type(ctx.get('exception')).__name__,
    }))
    temporary = tempfile.TemporaryDirectory(prefix='siro-fix013-current-audit-')
    root = Path(temporary.name)
    store = SQLiteStore(root / 'live.db')
    await store.initialize()
    def create(c):
        c.execute('CREATE TABLE audit_fixture(value TEXT NOT NULL)')
        c.execute("INSERT INTO audit_fixture VALUES ('latest')")
    await store.run_transaction(create)
    source = root / 'source.db'
    with closing(sqlite3.connect(source)) as c:
        apply_migrations(c, load_migrations())
        create(c)
        c.execute("UPDATE audit_fixture SET value='old-snapshot'")
        c.commit()
    source_before = source.read_bytes()
    enter, release, finished = threading.Event(), threading.Event(), threading.Event()
    original_migrate = module.apply_migrations
    original_restore = store._restore_sync
    restore = queued = None
    facts = {}
    def fail(c, migrations):
        enter.set()
        if not release.wait(3):
            raise RuntimeError('synthetic pause timed out')
        raise MigrationError('synthetic applied migration mismatch')
    def restore_sync(src, cancelled=None):
        try:
            original_restore(src, cancelled)
        finally:
            finished.set()
    def queued_write(c):
        c.execute("UPDATE audit_fixture SET value='queued-after-join'")
    module.apply_migrations = fail
    store._restore_sync = restore_sync
    try:
        restore = asyncio.create_task(store.restore_from(source))
        await event_wait(enter)
        queued = asyncio.create_task(store.run_transaction(queued_write))
        await asyncio.sleep(.01)
        restore.cancel()
        await asyncio.sleep(.01)
        facts['first_cancel_task_done'] = restore.done()
        facts['first_cancel_writer_lock_held'] = store._writer_lock.locked()
        facts['first_cancel_queued_writer_done'] = queued.done()
        restore.cancel()
        await asyncio.sleep(.01)
        facts['second_cancel_task_done'] = restore.done()
        facts['second_cancel_writer_lock_held'] = store._writer_lock.locked()
        facts['second_cancel_queued_writer_done'] = queued.done()
        release.set()
        try:
            await asyncio.wait_for(restore, 3)
        except BaseException as error:
            facts['caller_error_type'] = type(error).__name__
        facts['thread_finished_when_caller_returned'] = finished.is_set()
        with closing(sqlite3.connect(store.path)) as c:
            facts['live_before_queued_join'] = c.execute('SELECT value FROM audit_fixture').fetchone()[0]
        await asyncio.wait_for(queued, 3)
        with closing(sqlite3.connect(store.path)) as c:
            facts['live_after_queued_join'] = c.execute('SELECT value FROM audit_fixture').fetchone()[0]
        facts['source_main_bytes_unchanged'] = source.read_bytes() == source_before
        await asyncio.sleep(.01)
        facts['loop_exception_contexts'] = messages
        facts['writer_lock_after_join'] = store._writer_lock.locked()
    finally:
        release.set()
        if restore is not None:
            await asyncio.gather(restore, return_exceptions=True)
        if queued is not None:
            await asyncio.gather(queued, return_exceptions=True)
        module.apply_migrations = original_migrate
        store._restore_sync = original_restore
        loop.set_exception_handler(handler)
        temporary.cleanup()
    return {
        'python': sys.version.split()[0], 'sqlite': sqlite3.sqlite_version,
        'source_sha256': hashlib.sha256(Path('src/siro/persistence/sqlite.py').read_bytes()).hexdigest(),
        'synthetic_fixture_root': str(root), 'fixture_root_removed': not root.exists(),
        'current_source_cancel_then_primary_migration_failure': facts,
    }

if __name__ == '__main__':
    result = asyncio.run(run())
    out = Path('/tmp/siro-fix013-current-boundary-audit.json')
    out.write_text(json.dumps(result, indent=2)+'\n')
    print(out.read_text())
