from __future__ import annotations
import contextlib
import hashlib
import io
import json
import os
import select
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from siro import cli
from siro.adapters import data_ownership as owner
from siro.persistence.sqlite import apply_migrations,load_migrations

SELF=Path(__file__).resolve()

def seed(path,value):
    path.parent.mkdir()
    with contextlib.closing(sqlite3.connect(path)) as connection:
        apply_migrations(connection,load_migrations())
        connection.execute('CREATE TABLE destination_audit(value TEXT)')
        connection.execute('INSERT INTO destination_audit VALUES (?)',(value,))
        connection.commit()

def state(path):
    with contextlib.closing(sqlite3.connect(path)) as connection:
        return connection.execute('SELECT value FROM destination_audit').fetchone()[0]

def worker(domain,database):
    owner._owner_directory=lambda:domain
    with owner.exclusive_data_owner(database):
        with contextlib.closing(sqlite3.connect(database)) as connection:
            print('HELD '+connection.execute('SELECT value FROM destination_audit').fetchone()[0],flush=True)
            sys.stdin.read(1)
            print('OWNED_CONNECTION '+connection.execute('SELECT value FROM destination_audit').fetchone()[0],flush=True)

def run():
    temp=tempfile.TemporaryDirectory(prefix='siro-d50-destination-audit-')
    root=Path(temp.name)
    source=root/'source'/'siro.db'
    target=root/'target'/'siro.db'
    domain=root/'coordination'
    seed(source,'source-snapshot')
    seed(target,'foreign-managed-latest')
    before_inode=target.stat().st_ino
    process=None
    facts={'source_sha256':{str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['src/siro/adapters/data_ownership.py','src/siro/cli.py','src/siro/services/presentation/gateway.py']},'target_before':state(target)}
    try:
        env={k:v for k,v in os.environ.items() if not k.startswith('SIRO_') and k not in {'GROQ_API_KEY','OPENAI_API_KEY'}}
        process=subprocess.Popen([sys.executable,str(SELF),'worker',str(domain),str(target)],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        assert select.select([process.stdout],[],[],3)[0], 'synthetic target handshake timeout'
        facts['target_holder_ready']=process.stdout.readline().strip()
        with patch.object(owner,'_owner_directory',return_value=domain):
            try:
                with owner.exclusive_data_owner(target):
                    facts['target_busy_before_backup']=False
            except owner.DataOwnerBusyError:
                facts['target_busy_before_backup']=True
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                facts['cli_exit']=cli.main(['backup','--data',str(source.parent),str(target)])
            facts['cli_stdout']=json.loads(output.getvalue())
            facts['target_after_backup']=state(target)
            facts['target_inode_changed']=target.stat().st_ino != before_inode
            facts['target_holder_alive_after_backup']=process.poll() is None
            try:
                with owner.exclusive_data_owner(target):
                    facts['target_busy_after_backup']=False
            except owner.DataOwnerBusyError:
                facts['target_busy_after_backup']=True
        stdout,stderr=process.communicate(input='x',timeout=3)
        facts['holder_exit']=process.returncode
        facts['holder_remaining_stdout']=stdout.strip()
        facts['holder_stderr_present']=bool(stderr)
    finally:
        if process is not None and process.poll() is None:
            try:
                process.communicate(input='x',timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=3)
        temp.cleanup()
    result={'python':sys.version.split()[0],'sqlite':sqlite3.sqlite_version,'synthetic_root':str(root),'root_removed':not root.exists(),'actual_cli_backup_foreign_managed_destination':facts}
    output=Path('/tmp/siro-d50-backup-destination-probe.json')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(output.read_text())

if __name__=='__main__':
    if len(sys.argv)>1:
        worker(Path(sys.argv[2]),Path(sys.argv[3]))
    else:
        run()
