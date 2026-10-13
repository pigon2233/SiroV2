"""Isolated real network Gateway diagnostic smoke; no provider requests or tools."""
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

root=Path.cwd()
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0))
    port=sock.getsockname()[1]
with tempfile.TemporaryDirectory(prefix='rt007-main-') as directory:
    env={k:v for k,v in os.environ.items() if not k.startswith('SIRO_') and k!='GROQ_API_KEY'}
    env.update(SIRO_RUNTIME_PROFILE='candidate',SIRO_DATA_DIR=directory,SIRO_GATEWAY_PORT=str(port))
    with (Path(directory)/'gateway.log').open('wb') as log:
        child=subprocess.Popen([str(root/'.venv/bin/siro-gateway')],env=env,stdout=log,stderr=log)
        try:
            base=f'http://127.0.0.1:{port}'
            deadline=time.monotonic()+20
            while True:
                assert child.poll() is None
                try:
                    with urllib.request.urlopen(base+'/health/live',timeout=1) as response:
                        assert json.load(response)=={'state':'alive'}
                    break
                except (urllib.error.URLError,TimeoutError):
                    assert time.monotonic()<deadline
                    time.sleep(.1)
            session=urllib.request.Request(base+'/v1/session',data=b'',method='POST',
                                           headers={'Origin':'http://127.0.0.1:8000'})
            with urllib.request.urlopen(session) as response:
                token=json.load(response)['token']
            headers={'Authorization':f'Bearer {token}'}
            with urllib.request.urlopen(urllib.request.Request(base+'/v1/runtime',headers=headers)) as response:
                before=json.load(response)
            assert before['runtime_profile']=='candidate' and before['catalog_enabled']
            assert before['configuration_source']=='gateway_env_and_defaults'
            assert before['routes']['model']=='offline'
            request=urllib.request.Request(base+'/v1/kill-switches/tools',data=b'{"enabled":false}',
                        headers={**headers,'Content-Type':'application/json'},method='PUT')
            with urllib.request.urlopen(request) as response:
                assert json.load(response)['enabled'] is False
            with urllib.request.urlopen(urllib.request.Request(base+'/v1/runtime',headers=headers)) as response:
                after=json.load(response)
            assert not any(t['available'] for t in after['tools'])
            print(json.dumps({'network_startup':True,'profile':before['runtime_profile'],
                'catalog_enabled':before['catalog_enabled'],
                'tools':[t['name'] for t in before['tools']],
                'tools_off_all_unavailable':True}))
        finally:
            if child.poll() is None:child.terminate()
            child.wait(timeout=10)
            print(json.dumps({'shutdown_exit':child.returncode}))
