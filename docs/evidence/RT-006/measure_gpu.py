"""Synthetic local GPU lifecycle acceptance; never save reference or rendered audio."""
import asyncio
import hashlib
import io
import json
import tempfile
import time
from pathlib import Path

import soundfile as sf

from siro.services.audio.tts import QwenReferenceTTS


async def main():
    root = Path.cwd()
    reference = root / '.siro-data/qwen3-siro-anime-daughter-v1.wav'
    digest = hashlib.sha256(reference.read_bytes()).hexdigest()
    metrics = {'reference_before': digest, 'renders': []}
    with tempfile.TemporaryDirectory(prefix='rt006-gpu-') as temporary:
        tts = QwenReferenceTTS(root / '.siro-data/qwen-tts-venv/bin/python',
            root / 'scripts/qwen_tts_worker.py',root / '.siro-data/models/qwen3-tts-0.6b-base',
            reference,'爸爸，你回來啦？我等你好久了。今天有沒有發生什麼有趣的事？',
            Path(temporary),lifecycle=True,startup_timeout=180,render_timeout=180)
        try:
            for _ in range(2):
                start=time.monotonic()
                audio=await tts.render('爸爸，我在這裡。')
                info=sf.info(io.BytesIO(audio))
                metrics['renders'].append({'seconds':time.monotonic()-start,
                    'bytes':len(audio),'sha256':hashlib.sha256(audio).hexdigest(),
                    'format':info.format,'subtype':info.subtype,'sample_rate':info.samplerate,
                    'frames':info.frames,'pid':tts._process.pid})
            old=tts._process
            task=asyncio.create_task(tts.render('這是一段用來檢查取消的合成語句，今天的天空很美麗。'))
            await asyncio.sleep(.5)
            start=time.monotonic()
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
            assert old.returncode is not None and tts._process is None
            metrics['cancel_seconds']=time.monotonic()-start
            metrics['old_reaped']=not Path('/proc',str(old.pid)).exists()
            audio=await tts.render('爸爸，我在這裡。')
            metrics['restart_pid']=tts._process.pid
            assert metrics['restart_pid']!=old.pid
            assert hashlib.sha256(audio).hexdigest()==metrics['renders'][0]['sha256']
            last=tts._process
        finally:await tts.close()
        metrics['final_reaped']=not Path('/proc',str(last.pid)).exists()
    metrics['reference_after']=hashlib.sha256(reference.read_bytes()).hexdigest()
    assert metrics['reference_after']==digest
    print(json.dumps(metrics,ensure_ascii=False,indent=2))

asyncio.run(main())
