from __future__ import annotations
import argparse, asyncio, hashlib, importlib.util, json, sqlite3, sys, tempfile, threading
from contextlib import closing
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--store-source', type=Path, default=Path('src/siro/persistence/sqlite.py'))
parser.add_argument('--output', type=Path)
args = parser.parse_args()
source = args.store_source.resolve()
spec = importlib.util.spec_from_file_location('siro_boundary_store_snapshot', source)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
SQLiteStore, apply_migrations, load_migrations = module.SQLiteStore, module.apply_migrations, module.load_migrations
MigrationError = module.MigrationError

class StopCopy(Exception): pass

root = Path(tempfile.mkdtemp(prefix='siro-fix013-boundary-'))
report = {'python':sys.version.split()[0], 'sqlite':sqlite3.sqlite_version, 'temporary_root':str(root), 'private_data_read':False, 'store_source':str(source), 'store_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(), 'probes':[]}

def digest(path):
    return {s:hashlib.sha256(Path(str(path)+s).read_bytes()).hexdigest() if Path(str(path)+s).exists() else None for s in ('','-wal')}

def marker(path):
    with closing(sqlite3.connect(path)) as c:
        return c.execute('SELECT value FROM boundary_marker').fetchone()[0]

def prepared(path,value):
    with closing(sqlite3.connect(path)) as c:
        apply_migrations(c,load_migrations())
        c.execute('CREATE TABLE boundary_marker(value TEXT)')
        c.execute('INSERT INTO boundary_marker VALUES (?)',(value,)); c.commit()

async def current_prevalidation():
    folder=root/'prevalidation'; folder.mkdir(); live=folder/'live.db'; backup=folder/'source.db'
    prepared(live,'latest'); prepared(backup,'old-snapshot')
    with closing(sqlite3.connect(backup)) as c:
        c.execute("UPDATE schema_migrations SET checksum='synthetic-invalid-checksum' WHERE version=1"); c.commit()
    source_before=digest(backup)
    store=SQLiteStore(live); failure=None
    try: await store.restore_from(backup)
    except Exception as e: failure=type(e).__name__
    report['probes'].append({'name':'selected-source-prevalidation-order','failure':failure,'live_marker':marker(live),'latest_retained':marker(live)=='latest','source_unchanged':digest(backup)==source_before})


def copy_callback(mode,abort):
    folder=root/(mode+'-'+abort); folder.mkdir(); source=folder/'source.db'; live=folder/'live.db'
    with closing(sqlite3.connect(source)) as c:
        c.execute('CREATE TABLE boundary_marker(value TEXT)');c.execute("INSERT INTO boundary_marker VALUES ('old-snapshot')")
        c.execute('CREATE TABLE padding(value BLOB)'); c.executemany('INSERT INTO padding VALUES (?)',[(b'x'*8192,)]*512); c.commit()
    keeper=sqlite3.connect(live)
    keeper.execute('PRAGMA journal_mode='+mode)
    keeper.execute('CREATE TABLE boundary_marker(value TEXT)');keeper.execute("INSERT INTO boundary_marker VALUES ('latest')");keeper.commit()
    baseline=digest(live); events=[]; failure=None
    def progress(status,remaining,total):
        events.append([status,remaining,total])
        if (abort=='partial' and remaining>0) or (abort=='done' and status==sqlite3.SQLITE_DONE):
            raise StopCopy(abort)
    try:
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src, closing(sqlite3.connect(live)) as dst:
            src.backup(dst,pages=16,progress=progress,sleep=0.01)
    except Exception as e: failure=type(e).__name__
    result={'name':'backup-progress-'+mode+'-'+abort,'failure':failure,'first_callback':events[0],'last_callback':events[-1],'callbacks':len(events),'live_marker':marker(live),'latest_retained':marker(live)=='latest','main_wal_bytes_unchanged':digest(live)==baseline}
    keeper.close(); report['probes'].append(result)

async def cancellation(owner):
    folder=root/owner;folder.mkdir(); live=folder/'live.db';source=folder/'source.db'
    prepared(live,'latest');prepared(source,'old-snapshot');store=SQLiteStore(live)
    started,release,finished=threading.Event(),threading.Event(),threading.Event()
    cancel_flag=threading.Event(); original=store._restore_sync; thread_failure=[]
    def blocking(path):
        started.set()
        try:
            if not release.wait(3): raise TimeoutError('probe release missing')
            if owner=='guarded-prototype' and cancel_flag.is_set(): raise StopCopy('cancel before live copy')
            original(path)
        except BaseException as e:
            thread_failure.append(type(e).__name__); raise
        finally: finished.set()
    store._restore_sync=blocking
    async def guarded():
        async with store._writer_lock:
            job=asyncio.create_task(asyncio.to_thread(store._restore_sync,source))
            cancelled=False
            while not job.done():
                try: await asyncio.wait((job,))
                except asyncio.CancelledError:
                    cancelled=True;cancel_flag.set()
                except StopCopy: break
            try: job.result()
            except StopCopy:
                if not cancelled: raise
            if cancelled: raise asyncio.CancelledError
    task=asyncio.create_task(store.restore_from(source) if owner=='selected-source-owner' else guarded())
    assert await asyncio.to_thread(started.wait,2)
    task.cancel(); await asyncio.sleep(0.02); first_lock=store._writer_lock.locked(); first_done=task.done()
    def late_write(c): c.execute("UPDATE boundary_marker SET value='after-cancel-write'")
    writer=asyncio.create_task(store.run_transaction(late_write)); await asyncio.sleep(0.02)
    writer_done_before_release=writer.done(); second_cancel=task.cancel();await asyncio.sleep(0.02)
    second_lock=store._writer_lock.locked(); release.set()
    outcome=await asyncio.gather(task,return_exceptions=True);await writer
    assert await asyncio.to_thread(finished.wait,2)
    report['probes'].append({'name':owner,'first_cancel_task_done':first_done,'writer_lock_held_after_first_cancel':first_lock,'writer_completed_before_restore_join':writer_done_before_release,'second_cancel_accepted':second_cancel,'writer_lock_held_after_second_cancel':second_lock,'parent_outcome':type(outcome[0]).__name__,'thread_failure':thread_failure,'live_marker_after_both':marker(live)})

def prepared_selected(path,value,selected):
    with closing(sqlite3.connect(path)) as c:
        apply_migrations(c,selected)
        c.execute('CREATE TABLE boundary_marker(value TEXT)')
        c.execute('INSERT INTO boundary_marker VALUES (?)',(value,));c.commit()

def candidate_ready(candidate):
    migrations = load_migrations()
    with closing(sqlite3.connect(candidate)) as c:
        applied=list(c.execute('SELECT version,name,checksum FROM schema_migrations ORDER BY version'))
        expected=[(m.version,m.name,m.checksum) for m in migrations]
        if applied != expected[:len(applied)]:raise MigrationError('unsupported or modified migration ledger')
        apply_migrations(c,migrations)
        assert list(c.execute('SELECT version,name,checksum FROM schema_migrations ORDER BY version'))==expected
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'

def prevalidated(mode):
    migrations = load_migrations()
    folder=root/mode;folder.mkdir();source=folder/'source.db';live=folder/'live.db';candidate=folder/'owned.db'
    prepared_selected(source,'old-snapshot',migrations[:1]);prepared_selected(live,'latest',migrations)
    with closing(sqlite3.connect(source)) as c:
        if mode=='checksum':c.execute("UPDATE schema_migrations SET checksum='bad' WHERE version=1")
        if mode=='future':c.execute("INSERT INTO schema_migrations VALUES (999,'future','future','synthetic')")
        if mode=='migration-sql-failure':c.execute('CREATE TABLE identities(id TEXT)')
        c.commit()
    before=digest(source);live_before=digest(live);failure=None
    try:
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src, closing(sqlite3.connect(candidate)) as dst:
            src.backup(dst,pages=16)
        candidate_ready(candidate)
        with closing(sqlite3.connect(candidate.as_uri()+'?mode=ro',uri=True)) as src, closing(sqlite3.connect(live)) as dst:
            src.backup(dst,pages=16)
    except Exception as e:failure=type(e).__name__
    count=None
    with closing(sqlite3.connect(live.as_uri()+'?mode=ro',uri=True)) as c:count=c.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0]
    report['probes'].append({'name':mode,'failure':failure,'source_bytes_unchanged':digest(source)==before,'live_bytes_unchanged':digest(live)==live_before,'live_marker':marker(live),'live_migration_count':count,'expected_migration_count':len(migrations)})


async def main():
    await current_prevalidation()
    for mode in ('DELETE','WAL'):
        for abort in ('partial','done'): copy_callback(mode,abort)
    await cancellation('selected-source-owner')
    await cancellation('guarded-prototype')
    for mode in ('valid-old','checksum','future','migration-sql-failure'):
        prevalidated(mode)

try:
    asyncio.run(main())
finally:
    import shutil
    for child in root.iterdir():
        if child.is_dir():shutil.rmtree(child)
    report['database_fixtures_removed']=all(not x.is_dir() for x in root.iterdir())
    root.rmdir()
    report['database_fixtures_removed'] = not root.exists()
    if args.output is not None:
        args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
