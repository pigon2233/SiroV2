import asyncio,sys,os,json,tempfile,time,platform
from pathlib import Path
from siro.services.tools.execution import execute_bounded_argv

def rss():
 return next(int(x.split()[1])*1024 for x in Path('/proc/self/status').read_text().splitlines() if x.startswith('VmRSS:'))
async def main():
 base=rss(); samples=[base]; stopped=asyncio.Event()
 async def monitor():
  while not stopped.is_set():
   samples.append(rss()); await asyncio.sleep(.001)
 task=asyncio.create_task(monitor()); started=time.monotonic()
 with tempfile.TemporaryDirectory() as d:
  result=await execute_bounded_argv((sys.executable,'-c',"import os; b=b'x'*65536; [(os.write(1,b),os.write(2,b)) for _ in range(800)]"),cwd=Path(d),environment=os.environ.copy(),timeout=20)
 stopped.set(); await task
 report={'profile':'candidate','generated_bytes':100*1024*1024,'retained_bytes':len(result['stdout'].encode())+len(result['stderr'].encode()),'truncated':result['truncated'],'returncode':result['returncode'],'rss_baseline_bytes':base,'rss_peak_bytes':max(samples),'rss_delta_bytes':max(samples)-base,'sampling_interval_seconds':.001,'samples':len(samples),'elapsed_seconds':time.monotonic()-started,'python':platform.python_version(),'measurement_scope':'executor Python parent only; child RSS excluded'}
 assert report['retained_bytes']<=65536 and report['rss_delta_bytes']<32*1024*1024
 Path('docs/evidence/RT-004/measurement.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
asyncio.run(main())
