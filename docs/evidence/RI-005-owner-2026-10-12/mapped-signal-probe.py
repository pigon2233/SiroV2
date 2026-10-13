from __future__ import annotations
import asyncio
import hashlib
import json
import os
import select
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
import siro.adapters.data_ownership as owner
from siro.persistence.sqlite import SQLiteStore, apply_migrations, load_migrations

SELF=Path(__file__).resolve()

def wait_file(path, limit=3):
    end=time.monotonic()+limit
    while not path.exists():
        if time.monotonic()>end:
            raise RuntimeError('synthetic bounded handshake timeout')
        time.sleep(.002)

def worker(root):
    import siro.cli as cli
    owner._owner_directory=lambda:root/'domain'
    original_initialize=SQLiteStore._initialize_sync
    original_shutdown=asyncio.BaseEventLoop.shutdown_default_executor
    def initialize(self):
        original_initialize(self)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("UPDATE audit_fixture SET value='old-owner-write'")
            (root/'entered').touch()
            wait_file(root/'release',5)
            connection.commit()
        (root/'finished').touch()
    async def shutdown(self,*args,**kwargs):
        (root/'shutdown-entered').touch()
        return await original_shutdown(self,*args,**kwargs)
    SQLiteStore._initialize_sync=initialize
    asyncio.BaseEventLoop.shutdown_default_executor=shutdown
    try:
        return cli.main(['backup','--data',str(root/'data'),str(root/'backup.db')])
    except KeyboardInterrupt:
        print('INTERRUPTED',flush=True)
        return 130

def run():
    temporary=tempfile.TemporaryDirectory(prefix='siro-d50-mapped-audit-')
    root=Path(temporary.name)
    (root/'data').mkdir()
    database=root/'data'/'siro.db'
    with closing(sqlite3.connect(database)) as c:
        apply_migrations(c,load_migrations())
        c.execute('CREATE TABLE audit_fixture(value TEXT)')
        c.execute("INSERT INTO audit_fixture VALUES ('latest')")
        c.commit()
    environment={key:value for key,value in os.environ.items() if not key.startswith('SIRO_') and key not in {'GROQ_API_KEY','OPENAI_API_KEY'}}
    process=None
    facts={'adapter_sha256_at_start':hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest()}
    try:
        process=subprocess.Popen([sys.executable,str(SELF),'worker',str(root)],env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        wait_file(root/'entered')
        process.send_signal(signal.SIGINT)
        wait_file(root/'shutdown-entered')
        process.send_signal(signal.SIGINT)
        time.sleep(.03)
        process.send_signal(signal.SIGINT)
        time.sleep(.03)
        facts['child_alive_after_three_sigint']=process.poll() is None
        facts['old_db_work_pending']=not (root/'finished').exists()
        with patch.object(owner,'_owner_directory',return_value=root/'domain'):
            try:
                with owner.exclusive_data_owner(database):
                    facts['second_owner_busy_while_old_io_pending']=False
            except owner.DataOwnerBusyError:
                facts['second_owner_busy_while_old_io_pending']=True
        (root/'release').touch()
        stdout,stderr=process.communicate(timeout=5)
        facts['child_exit']=process.returncode
        facts['child_stdout']=stdout.strip()
        facts['child_stderr_present']=bool(stderr)
        facts['old_db_work_finished_before_next_owner']=(root/'finished').exists()
        with patch.object(owner,'_owner_directory',return_value=root/'domain'):
            with owner.exclusive_data_owner(database):
                with closing(sqlite3.connect(database)) as c:
                    facts['value_before_next_write']=c.execute('SELECT value FROM audit_fixture').fetchone()[0]
                    c.execute("UPDATE audit_fixture SET value='next-owner-write'")
                    c.commit()
        time.sleep(.03)
        with closing(sqlite3.connect(database)) as c:
            facts['final_value']=c.execute('SELECT value FROM audit_fixture').fetchone()[0]
        facts['backup_created_after_cancel']=(root/'backup.db').exists()
    finally:
        (root/'release').touch()
        if process is not None and process.poll() is None:
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=3)
        temporary.cleanup()
    result={'python':sys.version.split()[0],'sqlite':sqlite3.sqlite_version,'synthetic_root':str(root),'root_removed':not root.exists(),'actual_mapped_cli_backup_three_sigint':facts}
    output=Path('/tmp/siro-d50-mapped-audit.json')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(output.read_text())

if __name__=='__main__':
    if len(sys.argv)>1:
        raise SystemExit(worker(Path(sys.argv[2])))
    run()
