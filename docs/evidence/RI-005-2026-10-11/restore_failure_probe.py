"""Temporary-only explicit-restore failure probe; does not repair production."""
import asyncio,json,sqlite3,tempfile
from contextlib import closing
from pathlib import Path
from siro.persistence.sqlite import SQLiteStore

async def main():
    with tempfile.TemporaryDirectory(prefix='siro-d48-restore-probe-') as name:
        root=Path(name);live=SQLiteStore(root/'live.sqlite3');backup=SQLiteStore(root/'backup.sqlite3')
        await live.initialize();await backup.initialize()
        for store,value in ((live,'latest-synthetic'),(backup,'old-synthetic')):
            with closing(sqlite3.connect(store.path)) as connection,connection:
                connection.execute('CREATE TABLE acceptance(value TEXT)')
                connection.execute('INSERT INTO acceptance VALUES (?)',(value,))
        with closing(sqlite3.connect(backup.path)) as connection,connection:
            connection.execute('UPDATE schema_migrations SET checksum=? WHERE version=1',('0'*64,))
        before=live.path.read_bytes()
        error=None
        try:
            await live.restore_from(backup.path)
        except Exception as exc:
            error=type(exc).__name__
        with closing(sqlite3.connect(live.path)) as connection:
            value=connection.execute('SELECT value FROM acceptance').fetchone()[0]
        result={'status':'CONFIRMED_LOCAL_DEFECT','fixture':'temporary synthetic actual SQLiteStore explicit restore','error_type':error,'latest_data_retained':value=='latest-synthetic','old_snapshot_became_live':value=='old-synthetic','private_data_read':False,'live8026_accessed':False,'production_source_changed':False}
        assert error=='MigrationError' and value=='old-synthetic',result
    result['temporary_workspace_removed']=not root.exists()
    print(json.dumps(result,indent=2))
asyncio.run(main())
