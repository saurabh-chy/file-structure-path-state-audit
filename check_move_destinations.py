from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import pandas as pd, subprocess, tempfile, shutil
parser=argparse.ArgumentParser()
parser.add_argument('--work-dir', required=True, type=Path, help='Folder containing the sample CSVs and receiving outputs')
base=parser.parse_args().work_dir
s=pd.read_csv(base/'path_validation_sample_frame.csv')
r=pd.read_csv(base/'path_validation_sample_results.csv')
x=r.loc[r.candidate_outcome.eq('deep_path_removed_shallower_destination_present')].merge(s,on='sample_order')
def git(d,*a,timeout=180): return subprocess.run(['git','-C',str(d),*map(str,a)],capture_output=True,timeout=timeout)
def par(d,sha):
 z=git(d,'cat-file','-p',sha)
 return next((l.split()[1].decode() for l in z.stdout.splitlines() if l.startswith(b'parent ')),None)
def paths(d,sha):
 z=git(d,'ls-tree','-r','-z','--name-only',sha)
 if z.returncode: return None
 return {q.decode('utf8','surrogateescape') for q in z.stdout.split(b'\0') if q}
def check(q):
 d=Path(tempfile.mkdtemp(prefix='dest-audit-')); z={'sample_order':int(q.sample_order),'repo_id':q.repo_id_y,'target_path':q.target_path,'destination_path':q.candidate_new_path,'status':''}
 try:
  subprocess.run(['git','init','-q',str(d)],check=True); subprocess.run(['git','-C',str(d),'remote','add','origin',q.clone_url],check=True)
  f=git(d,'-c','protocol.version=2','fetch','--quiet','--depth=1','--filter=blob:none','origin',q.initiating_sha,q.candidate_sha)
  if f.returncode: z['status']='unavailable'; return z
  ep=par(d,q.initiating_sha); cp=par(d,q.candidate_sha)
  f=git(d,'-c','protocol.version=2','fetch','--quiet','--depth=1','--filter=blob:none','origin',ep,cp)
  if f.returncode: z['status']='parent_unavailable'; return z
  for name,sha in [('event_parent',ep),('event',q.initiating_sha),('candidate_parent',cp),('candidate',q.candidate_sha)]:
   ps=paths(d,sha)
   if ps is None: z['status']='tree_unavailable'; return z
   z[name+'_target_present']=str(q.target_path in ps)
   z[name+'_destination_present']=str(q.candidate_new_path in ps)
  z['status']='retrieved'; return z
 except Exception as e: z['status']='error'; z['error']=repr(e); return z
 finally: shutil.rmtree(d,ignore_errors=True)
out=[]
with ThreadPoolExecutor(max_workers=6) as p:
 fs=[p.submit(check,q) for _,q in x.iterrows()]
 for f in as_completed(fs): out.append(f.result())
y=pd.DataFrame(out).sort_values('sample_order'); y.to_csv(base/'path_validation_move_destination_results.csv',index=False)
print(y.to_string(index=False))
