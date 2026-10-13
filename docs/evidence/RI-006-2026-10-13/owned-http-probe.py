from pathlib import Path
import asyncio, json, os, signal, socket, sqlite3, subprocess, sys, tempfile, time, urllib.request
repo=Path('/home/jasonliao/文件/Siro/SiroV2')
evidence=repo/'docs/evidence/RI-006-2026-10-13'
sys.path.insert(0,str(repo/'src'))
sys.path.insert(0,str(repo/'tests/integration'))
from siro.persistence.sqlite import SQLiteStore
from siro.services.agent.runs import SQLiteAgentRunRepository
from test_runtime_status_context import failed_run
root=Path(tempfile.mkdtemp(prefix='ri6-http-'))
marker=evidence/'browser-stop'
marker.unlink(missing_ok=True)
async def seed():
    store=SQLiteStore(root/'siro.db'); await store.initialize()
    return await failed_run(SQLiteAgentRunRepository(store),session='browser',privacy='local_only',dispatched=True)
run_id=asyncio.run(seed())
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
assert port != 8026
env={'HOME':'/home/jasonliao','LANG':'C.UTF-8','PATH':'/usr/local/bin:/usr/bin:/bin',
     'PYTHONPATH':str(repo/'src'),'PYTHONDONTWRITEBYTECODE':'1','SIRO_DATA_DIR':str(root),
     'SIRO_RUNTIME_PROFILE':'candidate','SIRO_GATEWAY_PORT':str(port),
     'SIRO_CONTEXT_TOKEN_BUDGET_ENABLED':'0','SIRO_WORKSPACE_ENABLED':'0',
     'SIRO_MEMORY_ORGANIZATION_ENABLED':'0','SIRO_MEMORY_INGRESS_ENABLED':'0',
     'SIRO_CONTEXT_SUMMARY_ENABLED':'0','SIRO_BROWSER_SESSION_ENABLED':'0','SIRO_MODEL_RETRY_ENABLED':'0'}
state={'source_run_id':run_id,'url':f'http://127.0.0.1:{port}/','synthetic_data_only':True,
       'actual_main_composition':True,'root':str(root),'status':'STARTING'}
logpath=evidence/'owned-http-final.log'
with logpath.open('w') as log:
    process=subprocess.Popen([sys.executable,'-B','-c','from siro.services.presentation.gateway import main; main()'],
                             cwd=root,env=env,stdout=log,stderr=log,start_new_session=True)
    try:
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if process.poll() is not None: raise RuntimeError('owned server failed; inspect owned-http.log')
            try:
                with urllib.request.urlopen(state['url']+'health/ready',timeout=.3) as response:
                    if json.load(response).get('state')=='healthy': break
            except OSError: pass
            time.sleep(.05)
        else: raise TimeoutError('owned server readiness timed out')
        state['status']='READY'; state['pid']=process.pid
        (evidence/'owned-http-final-result.json').write_text(json.dumps(state,indent=2)+'\n')
        print(json.dumps(state),flush=True)
        deadline=time.monotonic()+600
        while not marker.exists() and time.monotonic()<deadline: time.sleep(.2)
    finally:
        process.terminate()
        try: code=process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill(); code=process.wait(timeout=3); state['forced_cleanup']=True
        state.update(exit_code=code,joined=True,status='STOPPED',shutdown_complete='Application shutdown complete.' in logpath.read_text())
        import shutil
        shutil.rmtree(root)
        marker.unlink(missing_ok=True)
        state['temporary_root_removed']=not root.exists()
        (evidence/'owned-http-final-result.json').write_text(json.dumps(state,indent=2)+'\n')
        print(json.dumps(state),flush=True)
