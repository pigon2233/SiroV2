from __future__ import annotations
import asyncio
import hashlib
import json
import os
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from siro.adapters import data_ownership as owner
from siro.persistence.sqlite import SQLiteStore,apply_migrations,load_migrations
from siro.config import SiroSettings

SELF=Path(__file__).resolve()
PATHS=['src/siro/adapters/data_ownership.py','src/siro/cli.py','src/siro/services/presentation/gateway.py','tests/integration/test_data_owner_callers.py','tests/integration/test_data_owner_lifecycle.py']

def wait_file(path,limit=6):
    end=time.monotonic()+limit
    while not path.exists():
        if time.monotonic()>end:
            raise RuntimeError('synthetic bounded handshake timeout')
        time.sleep(.002)

def worker(root):
    from siro import cli
    owner._owner_directory=lambda:root/'domain'
    tempfile.tempdir=str(root/'staging')
    original_backup=SQLiteStore._backup_sync
    original_shutdown=asyncio.BaseEventLoop.shutdown_default_executor
    original_finish=owner._DataOwner._finish
    def backup(self,destination):
        (root/'snapshot-path.json').write_text(json.dumps(str(destination)))
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
        return cli.main(['backup','--data',str(root/'data'),'--config',str(root/'settings.json'),str(root/'archive.zip')])
    except KeyboardInterrupt:
        print('INTERRUPTED',flush=True)
        return 130

def run():
    temporary=tempfile.TemporaryDirectory(prefix='siro-fix014-zip-joint-')
    root=Path(temporary.name)
    (root/'data').mkdir(); (root/'staging').mkdir()
    source=root/'data'/'siro.db'
    destination=root/'archive.zip'
    temporary_target=destination.with_suffix(destination.suffix+'.tmp')
    destination.write_bytes(b'synthetic-original-output')
    temporary_target.write_bytes(b'synthetic-original-temporary-output')
    output_before=destination.read_bytes()
    tmp_before=temporary_target.read_bytes()
    with closing(sqlite3.connect(source)) as c:
        apply_migrations(c,load_migrations())
        c.execute('CREATE TABLE zip_joint_fixture(value TEXT)')
        c.execute("INSERT INTO zip_joint_fixture VALUES ('source-snapshot')")
        c.commit()
    (root/'settings.json').write_text(SiroSettings().model_dump_json())
    process=None
    facts={'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in PATHS}}
    try:
        env={k:v for k,v in os.environ.items() if not k.startswith('SIRO_') and k not in {'GROQ_API_KEY','OPENAI_API_KEY'}}
        process=subprocess.Popen([sys.executable,str(SELF),'worker',str(root)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        wait_file(root/'backup-entered')
        snapshot=Path(json.loads((root/'snapshot-path.json').read_text()))
        facts['snapshot_parent_exists_before_cancel']=snapshot.parent.exists()
        facts['snapshot_parent_mode_before_cancel']=oct(stat.S_IMODE(snapshot.parent.stat().st_mode))
        facts['snapshot_parent_inode_before_cancel']=snapshot.parent.stat().st_ino
        process.send_signal(signal.SIGINT)
        wait_file(root/'shutdown-entered')
        process.send_signal(signal.SIGINT)
        wait_file(root/'owner-finishing')
        time.sleep(.03)
        process.send_signal(signal.SIGINT)
        time.sleep(.03)
        facts['child_alive_after_three_sigint']=process.poll() is None
        facts['actual_snapshot_io_pending']=not (root/'backup-finished').exists()
        facts['snapshot_parent_exists_while_old_io_pending']=snapshot.parent.exists()
        with patch.object(owner,'_owner_directory',return_value=root/'domain'):
            for name,path in [('source',source),('destination',destination),('temporary',temporary_target)]:
                try:
                    with owner.exclusive_data_owner(path):
                        facts[name+'_busy_while_snapshot_io_pending']=False
                except owner.DataOwnerBusyError:
                    facts[name+'_busy_while_snapshot_io_pending']=True
        (root/'release').touch()
        stdout,stderr=process.communicate(timeout=5)
        facts['child_exit']=process.returncode
        facts['child_joined']=process.poll() is not None
        facts['child_stdout']=stdout.strip()
        facts['child_stderr_present']=bool(stderr)
        facts['actual_snapshot_io_finished_before_next_owner']=(root/'backup-finished').exists()
        facts['destination_bytes_retained_after_cancel']=destination.read_bytes()==output_before
        facts['temporary_bytes_retained_after_cancel']=temporary_target.read_bytes()==tmp_before
        facts['snapshot_parent_exists_after_join']=snapshot.parent.exists()
        facts['snapshot_exists_after_join']=snapshot.exists()
        facts['known_owned_staging_entries_after_join']=[]
        for staged in sorted((root/'staging').rglob('*')):
            metadata=staged.lstat()
            facts['known_owned_staging_entries_after_join'].append({
                'path':str(staged), 'mode':oct(stat.S_IMODE(metadata.st_mode)),
                'inode':metadata.st_ino, 'size':metadata.st_size,
                'uid':metadata.st_uid, 'gid':metadata.st_gid, 'links':metadata.st_nlink,
                'regular':stat.S_ISREG(metadata.st_mode), 'directory':stat.S_ISDIR(metadata.st_mode),
                'group_readable':bool(metadata.st_mode&stat.S_IRGRP),
                'others_readable':bool(metadata.st_mode&stat.S_IROTH),
            })
        if snapshot.exists():
            with closing(sqlite3.connect(snapshot)) as c:
                facts['owned_private_snapshot_value_after_join']=c.execute('SELECT value FROM zip_joint_fixture').fetchone()[0]
        with patch.object(owner,'_owner_directory',return_value=root/'domain'):
            with owner.exclusive_data_owner(source,write_target=destination,temporary_write_target=temporary_target):
                facts['all_three_keys_acquired_after_join']=True
                destination.write_bytes(b'next-owner-output')
        time.sleep(.03)
        facts['next_owner_output_retained']=destination.read_bytes()==b'next-owner-output'
    finally:
        (root/'release').touch()
        if process is not None and process.poll() is None:
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.communicate(timeout=3)
        temporary.cleanup()
    result={'python':sys.version.split()[0],'sqlite':sqlite3.sqlite_version,'synthetic_root':str(root),'root_removed':not root.exists(),'actual_cli_zip_backup_three_key_three_sigint':facts}
    output=Path('/tmp/siro-fix014-zip-joint-signal.json')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(output.read_text())

if __name__=='__main__':
    if len(sys.argv)>1:
        raise SystemExit(worker(Path(sys.argv[2])))
    run()
