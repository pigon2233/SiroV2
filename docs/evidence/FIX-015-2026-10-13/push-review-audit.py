"""Bounded offline review of explicitly selected public push artifacts."""
from pathlib import Path
import collections
import ast
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
scope=json.loads((OUT/'push-candidate-scope.json').read_text())['paths']
scan=json.loads((OUT/'push-candidate-secrets.json').read_text())['results']
excluded=[]
selected=[]
for name in scope:
    p=Path(name)
    n=p.name
    redundant=(name.startswith('docs/evidence/') and p.suffix in {'.json','.log'} and (n.startswith('secrets-') or n.startswith('secret-scan') or n.startswith('developer-secret-scan') or n.startswith('push-')))
    future_red=name=='tests/integration/test_sqlite_backup_lifecycle.py'
    if redundant or future_red:
        excluded.append({'path':name,'reason':'NEXT_CARD_RED_TEST' if future_red else 'REDUNDANT_RAW_SECRET_SCAN_OR_REVIEW_OUTPUT'})
    else:
        assert not name.startswith(('.siro-data/','.codex/')),name
        assert p.suffix.lower() not in {'.wav','.png','.jpg','.jpeg','.mp3','.mp4','.db','.sqlite','.sqlite3'},name
        selected.append(name)
# Compute digests from actual public files only, not by trusting arbitrary recorded fields.
public=set(selected)
for b in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).split(b'\0'):
    if not b:continue
    name=b.decode();p=Path(name)
    if name.startswith(('.siro-data/','.codex/','config/body-assets/','models/','recordings/','screenshots/','runtime-data/')):continue
    if p.suffix.lower() in {'.wav','.png','.jpg','.jpeg','.mp3','.mp4','.db','.sqlite','.sqlite3','.pem','.key'}:continue
    if (ROOT/name).is_file():public.add(name)
known=collections.defaultdict(list)
for name in sorted(public):
    p=ROOT/name
    assert not p.is_symlink(),name
    known[hashlib.sha256(p.read_bytes()).hexdigest()].append(name)
derived=collections.defaultdict(list)
for name in sorted(public):
    p=ROOT/name
    if p.suffix=='.html':
        content=p.read_text()
        if '<script>' in content:
            script=content.split('<script>',1)[1].split('</script>',1)[0]
            derived[hashlib.sha256(script.encode()).hexdigest()].append({'file':name,'field':'literal main script content'})
    if p.suffix=='.py':
        try:tree=ast.parse(p.read_text())
        except (SyntaxError,UnicodeDecodeError):continue
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                derived[hashlib.sha256(node.value.encode()).hexdigest()].append({'file':name,'line':node.lineno,'field':'literal string constant'})
    if p.suffix=='.json':
        try:obj=json.loads(p.read_text())
        except (ValueError,UnicodeDecodeError):continue
        def walk(value,addr):
            if isinstance(value,dict):
                for key,child in value.items():walk(child,addr+[key])
            elif isinstance(value,list):
                for index,child in enumerate(value):walk(child,addr+[str(index)])
            elif isinstance(value,str) and addr and addr[-1]=='synthetic_text':
                derived[hashlib.sha256(value.encode()).hexdigest()].append({'file':name,'field':'.'.join(addr)})
        walk(obj,[])
gitids=set(subprocess.check_output(['git','rev-list','--all'],cwd=ROOT).decode().splitlines())
# Bind each previous contextual decision to that card's exact original detector fingerprint.
prior={}
for directory in sorted({(ROOT/name).parent for name in scope if name.startswith('docs/evidence/') and 'secret' in Path(name).name}):
    raws={}
    for p in directory.glob('*.json'):
        if 'secret' not in p.name:continue
        try:d=json.loads(p.read_text())
        except (ValueError,OSError):continue
        if isinstance(d,dict) and isinstance(d.get('results'),dict):
            for name,findings in d['results'].items():
                for f in findings:
                    if isinstance(f,dict):raws[(name,f.get('line_number'),f.get('type'),f.get('hashed_secret'))]=p
    for p in directory.glob('*review*.json'):
        if 'secret' not in p.name:continue
        try:d=json.loads(p.read_text())
        except (ValueError,OSError):continue
        if isinstance(d,dict) and d.get('status')!='PASS':continue
        records=d if isinstance(d,list) else d.get('findings',d.get('reviewed_findings',[]))
        if not isinstance(records,list):continue
        for record in records:
            if not isinstance(record,dict):continue
            classification=record.get('classification','')
            if 'FALSE_POSITIVE' not in classification:continue
            name=record.get('file');line=record.get('line')
            if not isinstance(name,str):continue
            if not name.startswith('docs/evidence/'):
                name=str((directory/name).relative_to(ROOT))
            reason=record.get('reason','')
            explicit=record.get('detector_fingerprint')
            for (rawname,rawline,kind,fp),rawpath in raws.items():
                if rawname!=name or rawline!=line:continue
                if explicit and explicit!=fp:continue
                if kind!='Hex High Entropy String' and classification!='SYNTHETIC_TEMPORARY_PATH_FALSE_POSITIVE':continue
                if kind=='Hex High Entropy String' and not (explicit or record.get('detector_fingerprint_matched') or any(x in reason.lower() for x in ('sha','digest','git commit'))):continue
                prior[(name,line,kind,fp)]={'review':str(p.relative_to(ROOT)),'raw_scan':str(rawpath.relative_to(ROOT)),'classification':classification}
reviewed=[]
unresolved=[]
for name in selected:
    findings=scan.get(name,[])
    if not findings:continue
    lines=(ROOT/name).read_text().splitlines()
    for f in findings:
        ln=f['line_number'];kind=f['type'];fp=f['hashed_secret'];line=lines[ln-1]
        entry={'file':name,'line':ln,'detector':kind,'detector_fingerprint':fp}
        tokens=[v for v in re.findall(r'(?<![a-fA-F0-9])[a-f0-9]{40}(?:[a-f0-9]{24})?(?![a-fA-F0-9])',line) if hashlib.sha1(v.encode()).hexdigest()==fp]
        if kind=='Hex High Entropy String' and len(tokens)==1 and tokens[0] in known:
            entry.update(classification='ACTUAL_PUBLIC_ARTIFACT_SHA256',artifact_paths=known[tokens[0]])
        elif kind=='Hex High Entropy String' and len(tokens)==1 and tokens[0] in derived:
            entry.update(classification='DERIVED_ACTUAL_PUBLIC_LITERAL_SHA256',artifact_fields=derived[tokens[0]])
        elif kind=='Hex High Entropy String' and len(tokens)==1 and tokens[0] in gitids:
            entry.update(classification='ACTUAL_REPOSITORY_GIT_COMMIT')
        elif (name,ln,kind,fp) in prior:
            entry.update(classification='EXACT_PREVIOUSLY_REVIEWED_FINGERPRINT',prior_binding=prior[(name,ln,kind,fp)])
        elif kind=='Secret Keyword' and 'synthetic' in line and hashlib.sha1(b'synthetic').hexdigest()==fp and ('api_key="synthetic"' in line or 'api_key="synthetic"' in line.replace('\\"','"')):
            entry.update(classification='EXPLICIT_SYNTHETIC_TEST_CREDENTIAL')
        elif kind=='Basic Auth Credentials' and name=='docs/evidence/FIX-002-2026-10-10/browser_scope_probe.py' and ln==175 and hashlib.sha1(b'synthetic-password').hexdigest()==fp and 'http://synthetic-user:synthetic-password@' in line:
            entry.update(classification='EXPLICIT_SYNTHETIC_BASIC_AUTH_NEGATIVE_FIXTURE',binding={'file':name,'line':165,'reason':'ephemeral127.0.0.1 origin built above fixture; literal synthetic password'})
        else:
            entry.update(classification='UNRESOLVED')
            unresolved.append(entry)
        reviewed.append(entry)
result={'status':'PASS' if not unresolved else 'NEEDS_REVIEW','selected_count':len(selected),'excluded_count':len(excluded),'finding_count':len(reviewed),'classification_counts':dict(collections.Counter(e['classification'] for e in reviewed)),'unresolved_count':len(unresolved),'scope_artifact':'push-candidate-scope.json','scan_artifact':'push-candidate-secrets.json','scope_file_sha256':hashlib.sha256((OUT/'push-candidate-scope.json').read_bytes()).hexdigest(),'scan_file_sha256':hashlib.sha256((OUT/'push-candidate-secrets.json').read_bytes()).hexdigest(),'private_runtime_or_codex_read':False,'media_read':False,'network_verification':False,'blanket_entropy_exemption':False,'selected_paths':selected,'excluded_paths':excluded,'reviewed_findings':reviewed}
(OUT/'push-review-result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
(OUT/'push-review-unresolved.json').write_text(json.dumps(unresolved,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'selected_paths','excluded_paths','reviewed_findings'}},indent=2))
for e in unresolved[:100]:print(e['file'],e['line'],e['detector'])
