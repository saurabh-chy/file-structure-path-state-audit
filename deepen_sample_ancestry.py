from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import pandas as pd, subprocess, tempfile, shutil
parser=argparse.ArgumentParser()
parser.add_argument('--work-dir', required=True, type=Path, help='Folder containing the sample CSVs and receiving outputs')
base=parser.parse_args().work_dir
s=pd.read_csv(base/'path_validation_sample_frame.csv')
a=pd.read_csv(base/'path_validation_ancestry_results.csv')
x=a[a.ancestry_status=='not_demonstrated_within_1000_depth'].merge(s,on=['sample_order','repo_id'])
def check(r):
 td=Path(tempfile.mkdtemp(prefix='ancestry-audit-deep-'))
 z={'sample_order':int(r.sample_order),'repo_id':r.repo_id,'ancestry_status_deep':''}
 try:
  subprocess.run(['git','init','-q',str(td)],check=True)
  subprocess.run(['git','-C',str(td),'remote','add','origin',r.clone_url],check=True)
  f=subprocess.run(['git','-C',str(td),'-c','protocol.version=2','fetch','--quiet','--depth=1','--filter=blob:none','origin',r.commit_id_initiating,r.correction_id],capture_output=True,timeout=180)
  if f.returncode: z['ancestry_status_deep']='initial_fetch_failed'; return z
  depth=max(2000,int(r.commit_index_candidate-r.commit_index_initiating)+1500)
  f=subprocess.run(['git','-C',str(td),'-c','protocol.version=2','fetch','--quiet',f'--deepen={depth}','--filter=tree:0','origin',r.correction_id],capture_output=True,timeout=600)
  if f.returncode: z['ancestry_status_deep']='deepen_failed'; z['error']=f.stderr.decode('utf8','replace')[-500:]; return z
  m=subprocess.run(['git','-C',str(td),'merge-base','--is-ancestor',r.commit_id_initiating,r.correction_id],capture_output=True,timeout=60)
  if m.returncode==0: z['ancestry_status_deep']=f'confirmed_within_{depth}_depth'
  else:
   shallow=subprocess.run(['git','-C',str(td),'rev-parse','--is-shallow-repository'],capture_output=True,text=True).stdout.strip()
   z['ancestry_status_deep']='not_ancestor_in_fetched_graph' if shallow=='false' else f'not_demonstrated_within_{depth}_depth'
  return z
 except Exception as ex: z['ancestry_status_deep']='error'; z['error']=repr(ex); return z
 finally: shutil.rmtree(td,ignore_errors=True)
out=[]
with ThreadPoolExecutor(max_workers=5) as pool:
 fs=[pool.submit(check,r) for _,r in x.iterrows()]
 for i,f in enumerate(as_completed(fs),1):
  out.append(f.result()); print('finished',i,'/',len(x),out[-1],flush=True)
r=pd.DataFrame(out); r.to_csv(base/'path_validation_ancestry_deep_results.csv',index=False)
print(r.ancestry_status_deep.value_counts().to_string())
