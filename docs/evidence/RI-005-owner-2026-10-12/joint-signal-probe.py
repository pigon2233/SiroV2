from __future__ import annotations
import asyncio
import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from siro.adapters import data_ownership as owner
from siro.persistence.sqlite import SQLiteStore,apply_migrations,load_migrations

SELF=Path(__file__).resolve()
PATHS=['src/siro/adapters/data_ownership.py','src/siro/cli.py','src/siro/services/presentation/gateway.py','tests/integration/test_data_owner_callers.py','tests/integration/test_data_owner_lifecycle.py']

def wait_file(path,limit=5):
    end=time.monotonic()+limit
    while not path.exists():
        if time.monotonic()>end:
            raise RuntimeError('synthetic bounded handshake timeout')
        time.sleep(.002)

def seed(path,value):
    path.parent.mkdir()
    with closing(sqlite3.connect(path)) as connection:
        apply_migrations(connection,load_migrations())
        connection.execute('CREATE TABLE joint_audit(value TEXT)')
        connection.execute('INSERT INTO joint_audit VALUES (?)',(value,))
        connection.commit()

def state(path):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute('SELECT value FROM joint_audit').fetchone()[0]

def worker(root):
    from siro import cli
    owner._owner_directory=lambda:root/'domain'
    original_backup=SQLiteStore._backup_sync
    original_shutdown=asyncio.BaseEventLoop.shutdown_default_executor
    original_finish=owner._DataOwner._finish
    def backup(self,destination):
        (root/'backup-entered').touch()
        wait_file(root/'release',8)
        try:
            original_backup(self,destination)
        finally:
            (root/'backup-finished').touch()
    async def shutdown(loop,*args,**kwargs):
        (root/'shutdown-entered').touch()
        return await original_shutdown(loop,*args,**kwargs)
    def finish(resource):
        (root/'owner-finishing').touch()
        return original_finish(resource)
    SQLiteStore._backup_sync=backup
    asyncio.BaseEventLoop.shutdown_default_executor=shutdown
    owner._DataOwner._finish=finish
    try:
        return cli.main(['backup','--data',str(root/'source'),str(root/'destination'/'siro.db')])
    except KeyboardInterrupt:
        print('INTERRUPTED',flush=True)
        return 130

def run():
    temporary=tempfile.TemporaryDirectory(prefix='siro-d50-joint-signal-')
    root=Path(temporary.name)
    source=root/'source'/'siro.db'
    destination=root/'destination'/'siro.db'
    seed(source,'source-snapshot')
    seed(destination,'destination-latest')
    process=None
    facts={'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in PATHS}}
    try:
        env={k:v for k,v in os.environ.items() if not k.startswith('SIRO_') and k not in {'GROQ_API_KEY','OPENAI_API_KEY'}}
        process=subprocess.Popen([sys.executable,str(SELF),'worker',str(root)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        wait_file(root/'backup-entered')
        process.send_signal(signal.SIGINT)
        wait_file(root/'shutdown-entered')
        process.send_signal(signal.SIGINT)
        wait_file(root/'owner-finishing')
        time.sleep(.03)
        process.send_signal(signal.SIGINT)
        time.sleep(.03)
        facts['child_alive_after_three_sigint']=process.poll() is None
        facts['actual_backup_io_pending']=not (root/'backup-finished').exists()
        facts['destination_before_release']=state(destination)
        with patch.object(owner,'_owner_directory',return_value=root/'domain'):
            for name,path in [('source',source),('destination',destination)]:
                try:
                    with owner.exclusive_data_owner(path):
                        facts[name+'_busy_while_backup_io_pending']=False
                except owner.DataOwnerBusyError:
                    facts[name+'_busy_while_backup_io_pending']=True
        (root/'release').touch()
        stdout,stderr=process.communicate(timeout=5)
        facts['child_exit']=process.returncode
        facts['child_stdout']=stdout.strip()
        facts['child_stderr_present']=bool(stderr)
        facts['actual_backup_io_finished_before_next_owner']=(root/'backup-finished').exists()
        facts['source_after_join']=state(source)
        facts['destination_after_join']=state(destination)
        with patch.object(owner,'_owner_directory',return_value=root/'domain'):
            with owner.exclusive_data_owner(source,write_target=destination):
                facts['both_keys_acquired_after_join']=True
                with closing(sqlite3.connect(destination)) as connection:
                    connection.execute("UPDATE joint_audit SET value='next-owner-write'")
                    connection.commit()
        time.sleep(.03)
        facts['destination_final_value']=state(destination)
    finally:
        (root/'release').touch()
        if process is not None and process.poll() is None:
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=3)
        temporary.cleanup()
    result={'python':sys.version.split()[0],'sqlite':sqlite3.sqlite_version,'synthetic_root':str(root),'root_removed':not root.exists(),'actual_mapped_cli_joint_backup_three_sigint':facts}
    output=Path('/tmp/siro-d50-joint-signal-probe.json')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(output.read_text())

if __name__=='__main__':
    if len(sys.argv)>1:
        raise SystemExit(worker(Path(sys.argv[2])))
    run()
