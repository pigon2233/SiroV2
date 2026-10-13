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
from siro.config import SiroSettings

SELF=Path(__file__).resolve()
PATHS=['src/siro/adapters/data_ownership.py','src/siro/cli.py','src/siro/services/presentation/gateway.py','tests/integration/test_data_owner_callers.py','tests/integration/test_data_owner_lifecycle.py']

def seed(path,value,version=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    with contextlib.closing(sqlite3.connect(path)) as c:
        apply_migrations(c,load_migrations() if version is None else load_migrations()[:version])
        c.execute('CREATE TABLE tmp_audit(value TEXT)')
        c.execute('INSERT INTO tmp_audit VALUES (?)',(value,))
        c.commit()

def worker(domain,target):
    owner._owner_directory=lambda:domain
    with owner.exclusive_data_owner(target):
        with contextlib.closing(sqlite3.connect(target)) as c:
            print('HELD '+c.execute('SELECT value FROM tmp_audit').fetchone()[0],flush=True)
            sys.stdin.read(1)
            try:
                value=c.execute('SELECT value FROM tmp_audit').fetchone()[0]
                print('OWNED_CONNECTION '+value,flush=True)
            except sqlite3.Error as error:
                print('CONNECTION_ERROR '+type(error).__name__,flush=True)

def run():
    temporary=tempfile.TemporaryDirectory(prefix='siro-fix014-tmp-audit-')
    root=Path(temporary.name)
    source=root/'data'/'siro.db'
    output=root/'backup.zip'
    foreign_tmp=output.with_suffix(output.suffix+'.tmp')
    domain=root/'domain'
    seed(source,'source-v1',1)
    seed(foreign_tmp,'foreign-tmp-latest')
    settings=root/'settings.json'
    settings.write_text(SiroSettings().model_dump_json())
    source_before=source.read_bytes()
    foreign_before=foreign_tmp.read_bytes()
    foreign_inode_before=foreign_tmp.stat().st_ino
    process=None
    facts={'source_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in PATHS}}
    try:
        env={k:v for k,v in os.environ.items() if not k.startswith('SIRO_') and k not in {'GROQ_API_KEY','OPENAI_API_KEY'}}
        process=subprocess.Popen([sys.executable,str(SELF),'worker',str(domain),str(foreign_tmp)],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        poller=select.poll()
        poller.register(process.stdout,select.POLLIN|select.POLLHUP)
        assert poller.poll(3000), 'synthetic owned-child handshake timeout'
        facts['holder_ready']=process.stdout.readline().strip()
        with patch.object(owner,'_owner_directory',return_value=domain):
            try:
                with owner.exclusive_data_owner(foreign_tmp):
                    facts['foreign_tmp_busy_before']=False
            except owner.DataOwnerBusyError:
                facts['foreign_tmp_busy_before']=True
            captured=io.StringIO()
            with contextlib.redirect_stdout(captured):
                facts['cli_exit']=cli.main(['backup','--data',str(source.parent),'--config',str(settings),str(output)])
            facts['cli_stdout']=json.loads(captured.getvalue())
            facts['source_main_bytes_retained']=source.read_bytes()==source_before
            with contextlib.closing(sqlite3.connect(source)) as c:
                facts['source_migration_versions_after']=[r[0] for r in c.execute('SELECT version FROM schema_migrations ORDER BY version')]
            facts['foreign_tmp_path_exists_after']=foreign_tmp.exists()
            facts['foreign_tmp_bytes_retained']=foreign_tmp.exists() and foreign_tmp.read_bytes()==foreign_before
            facts['foreign_tmp_inode_retained']=foreign_tmp.exists() and foreign_tmp.stat().st_ino==foreign_inode_before
            facts['destination_archive_created']=output.exists()
            facts['holder_alive_after']=process.poll() is None
            try:
                with owner.exclusive_data_owner(foreign_tmp):
                    facts['foreign_tmp_busy_after']=False
            except owner.DataOwnerBusyError:
                facts['foreign_tmp_busy_after']=True
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
        temporary.cleanup()
    result={'python':sys.version.split()[0],'sqlite':sqlite3.sqlite_version,'synthetic_root':str(root),'root_removed':not root.exists(),'actual_cli_zip_backup_foreign_tmp_owner':facts}
    p=Path('/tmp/siro-fix014-tmp-destination-probe.json')
    p.write_text(json.dumps(result,indent=2)+'\n')
    print(p.read_text())

if __name__=='__main__':
    if len(sys.argv)>1:
        worker(Path(sys.argv[2]),Path(sys.argv[3]))
    else:
        run()
