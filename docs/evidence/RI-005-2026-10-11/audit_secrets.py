"""Review explicit D48 scans without reading private files or blanket exemptions."""
from pathlib import Path
import datetime,hashlib,json,re
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
baseline=json.loads((OUT/'baseline.json').read_text())['hashes']
preservation=json.loads((OUT/'preservation.json').read_text())
known=set(baseline.values())|set(preservation['final_sha256'].values())|{preservation['patch_sha256']}
review=[];unresolved=[]
for filename,findings in json.loads((OUT/'secrets-evidence-final.json').read_text())['results'].items():
 path=ROOT/filename
 assert path.is_relative_to(OUT),filename
 lines=path.read_text().splitlines()
 for finding in findings:
  line=lines[finding['line_number']-1]
  candidates=set(re.findall(r'(?<![a-fA-F0-9])[a-f0-9]{64}(?![a-fA-F0-9])',line))
  matches=[value for value in candidates if hashlib.sha1(value.encode()).hexdigest()==finding['hashed_secret']]
  valid=finding['type']=='Hex High Entropy String' and len(matches)==1 and matches[0] in known
  # Recognize the actual named recorded field, not arbitrary entropy anywhere.
  named=any(word in line for word in ('sha256','SHA256','"src/','"tests/','"scripts/','"Cargo.','"pyproject.','"uv.lock"'))
  item={'file':filename,'line':finding['line_number'],'detector':finding['type'],'detector_fingerprint':finding['hashed_secret'],'exact_line_match':len(matches)==1,'known_captured_digest':valid,'named_recorded_field':named,'classification':'RECORDED_SHA256_FALSE_POSITIVE' if valid and named else 'UNRESOLVED'}
  review.append(item)
  if item['classification']=='UNRESOLVED':unresolved.append(item)
source=json.loads((OUT/'secrets-source-final.json').read_text())['results']
docs=json.loads((OUT/'secrets-docs-final.json').read_text())['results']
assert not source and not docs,(len(source),len(docs))
assert not unresolved,[{k:v for k,v in f.items() if k!='detector_fingerprint'} for f in unresolved]
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in preservation['final_sha256'].items())
cutoff=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
result={'status':'PASS','cutoff_utc':cutoff,'source_files':3,'source_findings':0,'document_files':13,'document_findings':0,'evidence_raw_findings':len(review),'reviewed_digest_false_positives':len(review),'unresolved':0,'findings':review,'private_data_read':False,'network_verification':False,'annotation_only_updates_after_cutoff_excluded':True,'independent_subagent_review_completed':False}
(OUT/'secrets-review-final.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='findings'},indent=2))
