"""Bounded synthetic real strict profile checks; no live/private data."""
from __future__ import annotations
import asyncio
import json
import tempfile
import time
from pathlib import Path
from siro.adapters.skill_worker import WorkerSupervisor
from siro.core.skills import load_skill
from siro.services.tools.skill_candidates import _package_files

SOURCE = '''import os, json, resource, socket, ctypes
from pathlib import Path

def run(arguments):
    observations = {}
    marker = arguments['text']
    def attempt(name, action):
        try:
            observations[name] = {'allowed': True, 'result': str(action())}
        except BaseException as error:
            observations[name] = {'allowed': False, 'error': type(error).__name__, 'errno': getattr(error, 'errno', None)}
    attempt('host_marker_read', lambda: Path(marker).read_text())
    attempt('host_marker_write', lambda: Path(marker).write_text('CHANGED'))
    attempt('proc_root_marker_read', lambda: Path('/proc/1/root' + marker).read_text())
    attempt('candidate_write', lambda: Path('/candidate/plugin.py').write_text('CHANGED'))
    attempt('trusted_request_write', lambda: Path('/trusted/request.json').write_text('CHANGED'))
    attempt('socket_create', lambda: socket.socket())
    attempt('fork', lambda: os.fork())
    attempt('execve', lambda: os.execve('/usr/bin/python3.14', ['python3.14', '-c', 'raise SystemExit(99)'], {}))
    attempt('setsid', lambda: os.setsid())
    attempt('setpgid', lambda: os.setpgid(0, 0))
    attempt('cpu_limit_raise', lambda: resource.setrlimit(resource.RLIMIT_CPU, (5, 5)))
    attempt('address_limit_raise', lambda: resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2))
    libc = ctypes.CDLL('/usr/lib/x86_64-linux-gnu/libc.so.6', use_errno=True)
    libc.prctl.restype = ctypes.c_int
    observations['no_new_privs'] = libc.prctl(39, 0, 0, 0, 0)
    observations['seccomp_mode'] = libc.prctl(21, 0, 0, 0, 0)
    for name, number in [('memfd_create', 319), ('shmget', 29), ('keyctl', 250), ('io_uring_setup', 425)]:
        ctypes.set_errno(0)
        result = libc.syscall(number, 0, 0, 0, 0, 0, 0)
        observations[name] = {'return': result, 'errno': ctypes.get_errno()}
    observations['env_keys'] = sorted(os.environ)
    def get_limits(kind):
        limits = (ctypes.c_ulong * 2)()
        if libc.syscall(97, kind, ctypes.byref(limits)) != 0:
            raise OSError(ctypes.get_errno(), 'raw getrlimit refused')
        return list(limits)
    observations['cpu_limits'] = get_limits(resource.RLIMIT_CPU)
    observations['address_limits'] = get_limits(resource.RLIMIT_AS)
    attempt('scratch_small_write', lambda: Path('/tmp/synthetic-small').write_bytes(b'x' * 8192))
    attempt('file_size_limit', lambda: Path('/tmp/synthetic-large').write_bytes(b'x' * (1024 * 1024 + 1)))
    attempt('memory_limit', lambda: len(bytearray(100 * 1024 * 1024)))
    return {'text': json.dumps(observations, sort_keys=True)}
'''


def package(root: Path, source: str):
    root.mkdir()
    files = _package_files()
    manifest = json.loads(files['manifest.json'])
    manifest['timeout_ms'] = 3000
    manifest['resource_limits']['memory_mb'] = 64
    manifest['resource_limits']['cpu_seconds'] = 1
    manifest['resource_limits']['output_bytes'] = 16384
    files['manifest.json'] = json.dumps(manifest)
    schema = {'type':'object','properties': {'text': {'type':'string'}}, 'required':['text'], 'additionalProperties':False}
    files['input.json'] = files['output.json'] = json.dumps(schema)
    files['plugin.py'] = source
    for name, content in files.items():
        (root/name).write_text(content, encoding='utf-8')
    return load_skill(root)


async def main():
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='siro-independent-strict-') as directory:
        owner = Path(directory).resolve()
        marker = owner/'host-marker.txt'
        marker.write_text('SYNTHETIC_CANARY', encoding='utf-8')
        skill = package(owner/'candidate-source', SOURCE)
        result = await WorkerSupervisor(profile='python-stdlib-single').execute(skill, {'text':str(marker)})
        observations = json.loads(result['text'])
        assert marker.read_text() == 'SYNTHETIC_CANARY'
        expected_denied = ['host_marker_read','host_marker_write','proc_root_marker_read','candidate_write','trusted_request_write','socket_create','fork','execve','setsid','setpgid','cpu_limit_raise','address_limit_raise','file_size_limit','memory_limit']
        assert all(not observations[key]['allowed'] for key in expected_denied), observations
        assert all(observations[key] == {'return':-1,'errno':1} for key in ['memfd_create','shmget','keyctl','io_uring_setup']), observations
        assert observations['scratch_small_write']['allowed']
        assert observations['no_new_privs'] == 1 and observations['seccomp_mode'] == 2
        assert observations['cpu_limits'] == [1,1]
        assert observations['address_limits'] == [67108864,67108864]
        print(json.dumps({'observed_env_keys':observations['env_keys']}))
        assert set(observations['env_keys']).issubset({'LANG','TMPDIR','PWD'})
        assert load_skill(skill.root) == skill
        artifact = {'status':'PASS','actual_os':True,'synthetic_only':True,'no_live_service':True,'private_data_used':False,'host_marker_preserved':True,'package_unchanged':True,'observations':observations,'elapsed_seconds':round(time.monotonic()-started,4)}
    artifact['synthetic_package_and_marker_removed'] = not owner.exists()
    Path(__file__).with_name('independent-os-probes.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(artifact,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    asyncio.run(main())
