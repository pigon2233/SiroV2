"""Local MCP protocol client; records only approved source graph responses."""
from __future__ import annotations
import json
import os
from pathlib import Path
import selectors
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).parent
LOG = []


def main() -> None:
    stderr = (EVIDENCE / 'mcp-analysis-stderr.log').open('w')
    process = subprocess.Popen(
        ['/usr/bin/python3', str(ROOT / 'scripts/codebase_memory.py'), 'serve'],
        cwd=ROOT, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
    )
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    buffer = b''
    counter = 0

    def request(method: str, params: dict) -> dict:
        nonlocal counter, buffer
        counter += 1
        message = {'jsonrpc': '2.0', 'id': counter, 'method': method, 'params': params}
        process.stdin.write((json.dumps(message) + '\n').encode()); process.stdin.flush()
        start = time.monotonic()
        while time.monotonic() - start < 60:
            if b'\n' not in buffer:
                if not selector.select(1):
                    if process.poll() is not None:
                        raise RuntimeError('MCP exited: ' + str(process.returncode))
                    continue
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError('MCP stdout ended')
                buffer += chunk
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                response = json.loads(line)
                if response.get('id') == counter:
                    LOG.append({'request': message, 'response': response,
                                'seconds': round(time.monotonic()-start, 6)})
                    return response
        raise TimeoutError(method)

    def call(name: str, arguments: dict) -> dict:
        return request('tools/call', {'name': name, 'arguments': arguments})

    try:
        initialize = request('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                              'clientInfo': {'name': 'SIRO-local-verifier', 'version': '1'}})
        assert 'result' in initialize, initialize
        process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        process.stdin.flush()
        tools = request('tools/list', {})['result']['tools']
        (EVIDENCE / 'mcp-tool-schemas.json').write_text(json.dumps(tools, indent=2)+'\n')
        assert len(tools) == 13, len(tools)
        assert not {'index_repository', 'manage_adr', 'delete_project', 'ingest_traces'} & {t['name'] for t in tools}
        call('list_projects', {})
        call('get_graph_schema', {'project': 'SiroV2'})
        call('get_architecture', {'project': 'SiroV2', 'aspects': ['all']})
        call('search_graph', {'project': 'SiroV2', 'name_pattern': '(respond|propose|retrieve|record_turn|publish_body_intent|create_turn)', 'limit': 80, 'format': 'json', 'max_output_tokens': 10000})
        call('get_architecture', {'project': 'SiroV2', 'aspects': ['cycles', 'hotspots', 'dependencies'], 'format': 'json'})
        call('query_graph', {'project': 'SiroV2', 'query': 'MATCH (n:File) RETURN n LIMIT 3', 'format': 'json'})
        call('query_graph', {'project': 'SiroV2', 'query': "MATCH (n:File) WHERE n.file_path CONTAINS '.siro-data' OR n.file_path CONTAINS '.env' OR n.file_path CONTAINS 'docs/evidence' RETURN n", 'format': 'json'})
        denied = call('index_repository', {'repo_path': '/workspace/projects/SiroV2'})
        assert 'error' in denied or denied.get('result', {}).get('isError'), denied
        (EVIDENCE / 'mcp-analysis.json').write_text(json.dumps(LOG, ensure_ascii=False, indent=2)+'\n')
    finally:
        if process.stdin:
            process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate(); process.wait(timeout=5)
        selector.close(); stderr.close()
        (EVIDENCE / 'mcp-analysis-cleanup.json').write_text(json.dumps({'returncode': process.returncode})+'\n')
    print(json.dumps({'server': initialize['result'].get('serverInfo'), 'tools': len(tools),
                      'calls': len(LOG), 'returncode': process.returncode}))


if __name__ == '__main__':
    main()
