"""Actual installed Gateway startup recovery with synthetic temporary data only."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

root = Path.cwd()
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
with tempfile.TemporaryDirectory(prefix='rt008-main-') as directory:
    environment = {k: v for k, v in os.environ.items() if not k.startswith('SIRO_') and k != 'GROQ_API_KEY'}
    fixture = subprocess.run([sys.executable, 'tests/fixtures/run_journal_crash.py', directory,
                              'before_observation'], env=environment, capture_output=True, timeout=20)
    assert fixture.returncode == 42
    marker = Path(directory) / 'effect.txt'
    before = marker.read_text()
    environment.update(SIRO_RUNTIME_PROFILE='candidate', SIRO_DATA_DIR=directory,
                       SIRO_GATEWAY_PORT=str(port))
    logfile = Path(directory) / 'gateway.log'
    with logfile.open('wb') as log:
        process = subprocess.Popen([str(root / '.venv/bin/siro-gateway')], env=environment,
                                   stdout=log, stderr=log)
        try:
            base = f'http://127.0.0.1:{port}'
            deadline = time.monotonic() + 20
            while True:
                assert process.poll() is None, logfile.read_text()
                try:
                    with urllib.request.urlopen(base + '/health/live', timeout=1) as response:
                        assert json.load(response) == {'state': 'alive'}
                    break
                except (urllib.error.URLError, TimeoutError):
                    assert time.monotonic() < deadline
                    time.sleep(.1)
            request = urllib.request.Request(base + '/v1/session', data=b'', method='POST',
                                              headers={'Origin': 'http://127.0.0.1:8000'})
            with urllib.request.urlopen(request) as response:
                token = json.load(response)['token']
            request = urllib.request.Request(base + '/v1/agent-runs/crash-session',
                                              headers={'Authorization': f'Bearer {token}'})
            with urllib.request.urlopen(request) as response:
                readback = json.load(response)
            assert readback['state'] == 'failed' and readback['error'] == 'outcome_unknown'
            assert readback['model_rounds'] == 1 and readback['tool_calls'] == 1
            assert [m['role'] for m in readback['messages']] == ['system', 'user', 'assistant', 'tool']
            assert marker.read_text() == before
            with urllib.request.urlopen(base + '/') as response:
                page = response.read().decode()
                assert '/v1/agent-runs/browser' in page and '結果未知' in page
            print(json.dumps({'actual_main_startup_recovery': True, 'unknown_visible': True,
                              'paired_messages': True, 'budgets_preserved': True,
                              'side_effect_file_unchanged': True, 'recovery_ui_served': True}))
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
            assert 'Application shutdown complete.' in logfile.read_text()
            print(json.dumps({'graceful_shutdown_log': True, 'exit': process.returncode}))
