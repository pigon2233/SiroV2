from __future__ import annotations
import errno
import fcntl
import json
import os
import select
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SELF = Path(__file__).resolve()

def locked(path):
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd)
        raise

def try_lock(path):
    try:
        fd = locked(path)
    except BlockingIOError:
        return False
    os.close(fd)
    return True

def line(process):
    ready, _, _ = select.select([process.stdout], [], [], 3)
    if not ready:
        raise RuntimeError('owned synthetic process did not signal within3s')
    return process.stdout.readline().strip()

def stop(process):
    if process.poll() is None:
        process.kill()
    process.wait(timeout=3)
    if process.stdin is not None:
        process.stdin.close()
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()

def child(mode, path):
    try:
        fd = locked(path)
    except BlockingIOError:
        print('busy', flush=True)
        return
    if mode in ('exec-cloexec', 'exec-inherit'):
        os.set_inheritable(fd, mode == 'exec-inherit')
        os.execv(sys.executable, [sys.executable, '-c', "import time;print('exec-ready',flush=True);time.sleep(20)"])
    print('acquired', flush=True)
    sys.stdin.readline()
    os.close(fd)


def fork_probe(path, unlock):
    fd = locked(path)
    ready_read, ready_write = os.pipe()
    gate_read, gate_write = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(ready_read)
        os.close(gate_write)
        os.write(ready_write, b'1')
        os.read(gate_read, 1)
        if unlock:
            fcntl.flock(fd, fcntl.LOCK_UN)
        else:
            os.close(fd)
        os.write(ready_write, b'2')
        os.read(gate_read, 1)
        os._exit(0)
    os.close(ready_write)
    os.close(gate_read)
    closed = False
    try:
        assert select.select([ready_read], [], [], 3)[0]
        assert os.read(ready_read, 1) == b'1'
        inheritable = os.get_inheritable(fd)
        if not unlock:
            os.close(fd)
            closed = True
        busy_before = not try_lock(path)
        os.write(gate_write, b'1')
        assert select.select([ready_read], [], [], 3)[0]
        assert os.read(ready_read, 1) == b'2'
        acquired_after = try_lock(path)
        os.write(gate_write, b'1')
        _, status = os.waitpid(pid, 0)
        pid = 0
        return {'parent_fd_inheritable': inheritable, 'contender_busy_before_child_action': busy_before,
                'contender_acquired_after_child_action': acquired_after, 'child_exit0': status == 0}
    finally:
        if pid:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        if not closed:
            os.close(fd)
        os.close(ready_read)
        os.close(gate_write)


def run():
    temp = tempfile.TemporaryDirectory(prefix='siro-d50-lock-')
    root = Path(temp.name)
    children = []
    result = {'python': sys.version.split()[0], 'kernel': os.uname().release,
              'synthetic_root': str(root), 'filesystem': subprocess.check_output(['stat','-f','-c','%T',str(root)],text=True).strip()}
    try:
        path = root / 'atomic.lock'
        for _ in range(4):
            children.append(subprocess.Popen([sys.executable,str(SELF),'child','hold',str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
        outcomes = [line(p) for p in children]
        result['four_simultaneous_contenders'] = {'outcomes':outcomes, 'exactly_one_winner':outcomes.count('acquired') == 1}
        winner = children[outcomes.index('acquired')]
        before = not try_lock(path)
        begin = time.monotonic()
        winner.kill()
        winner.wait(timeout=3)
        result['sigkill_release'] = {'busy_while_owner_alive':before, 'owner_exit':winner.returncode,
                                    'acquired_after_owner_join':try_lock(path), 'elapsed_ms':round((time.monotonic()-begin)*1000,3)}
        for p in children:
            stop(p)
        children.clear()
        result['fork_child_close_only'] = fork_probe(root / 'fork-close.lock', False)
        result['fork_child_unlock_releases_parent'] = fork_probe(root / 'fork-unlock.lock', True)
        for mode in ('exec-cloexec','exec-inherit'):
            p = subprocess.Popen([sys.executable,str(SELF),'child',mode,str(root / (mode+'.lock'))],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            children.append(p)
            assert line(p) == 'exec-ready'
            result[mode] = {'contender_acquired_while_replacement_alive':try_lock(root / (mode+'.lock'))}
            stop(p)
            children.clear()
        real = root / 'real'
        real.mkdir()
        alias = root / 'alias'
        alias.symlink_to(real, target_is_directory=True)
        fd = locked(real / 'same.lock')
        try:
            result['directory_symlink_alias'] = {'canonical_roots_same':alias.resolve() == real.resolve(),
                'same_lock_contender_busy':not try_lock(alias / 'same.lock')}
        finally:
            os.close(fd)
        lockfile = real / 'aliased.lock'
        lockfile.touch()
        symlink = root / 'lock-symlink'
        symlink.symlink_to(lockfile)
        try:
            nofollow = os.open(symlink, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError as error:
            result['symlink_lock_nofollow'] = {'errno':error.errno,'rejected':error.errno == errno.ELOOP}
        else:
            os.close(nofollow)
            result['symlink_lock_nofollow'] = {'rejected':False}
        hardlink = root / 'lock-hardlink'
        os.link(lockfile, hardlink)
        result['hardlink_stat'] = {'regular':stat.S_ISREG(lockfile.stat().st_mode),'link_count':lockfile.stat().st_nlink,
                                 'same_inode':lockfile.stat().st_ino == hardlink.stat().st_ino}
        fd = locked(root / 'never-unlink.lock')
        try:
            initial_inode = os.fstat(fd).st_ino
            (root / 'never-unlink.lock').unlink()
            other = locked(root / 'never-unlink.lock')
            try:
                result['unlink_recreate_split_owner'] = {'second_owner_acquired':True,
                            'different_inode':initial_inode != os.fstat(other).st_ino}
            finally:
                os.close(other)
        finally:
            os.close(fd)
        first = root / 'first-data'
        second = root / 'second-data'
        first.mkdir(); second.mkdir()
        (first / 'siro.db').write_bytes(b'synthetic-not-a-real-db')
        (second / 'siro.db').symlink_to(first / 'siro.db')
        fd = locked(first / '.naive-owner.lock')
        try:
            result['db_symlink_naive_parent_key_split'] = {
                'actual_db_targets_same':(first / 'siro.db').resolve() == (second / 'siro.db').resolve(),
                'naive_other_parent_lock_acquired':try_lock(second / '.naive-owner.lock')}
        finally:
            os.close(fd)
        result['network_filesystems_tested'] = False
    finally:
        for p in children:
            stop(p)
        temp.cleanup()
    result['fixture_root_removed'] = not root.exists()
    result['owned_processes_joined'] = True
    output = Path('/tmp/siro-d50-flock-probe.json')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(output.read_text())

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'child':
        child(sys.argv[2], sys.argv[3])
    else:
        run()
