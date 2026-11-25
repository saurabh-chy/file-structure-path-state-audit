from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import pandas as pd, subprocess, tempfile, shutil
parser=argparse.ArgumentParser()
parser.add_argument('--work-dir', required=True, type=Path, help='Folder containing the sample CSVs and receiving outputs')
base=parser.parse_args().work_dir
sample=pd.read_csv(base/'path_validation_sample_frame.csv')
results=pd.read_csv(base/'path_validation_sample_results.csv')
rows=sample.merge(results[['sample_order','fetch_status']],on='sample_order',how='inner')
rows=rows.loc[rows.fetch_status.eq('retrieved')]

def check(r):
  td=Path(tempfile.mkdtemp(prefix='ancestry-audit-'))
  out={'sample_order':int(r.sample_order),'repo_id':r.repo_id,'ancestry_status':'','error':''}
  try:
    subprocess.run(['git','init','-q',str(td)],check=True,timeout=20)
    subprocess.run(['git','-C',str(td),'remote','add','origin',r.clone_url],check=True,timeout=20)
    f=subprocess.run(['git','-C',str(td),'-c','protocol.version=2','fetch','--quiet','--depth=1','--filter=blob:none','origin',r.commit_id_initiating,r.correction_id],capture_output=True,timeout=180)
    if f.returncode:
      out['ancestry_status']='unavailable_initial_fetch'; out['error']=f.stderr.decode('utf8','replace')[-500:]; return out
    f=subprocess.run(['git','-C',str(td),'-c','protocol.version=2','fetch','--quiet','--deepen=1000','--filter=tree:0','origin',r.correction_id],capture_output=True,timeout=300)
    if f.returncode:
      out['ancestry_status']='unavailable_deepen'; out['error']=f.stderr.decode('utf8','replace')[-500:]; return out
    m=subprocess.run(['git','-C',str(td),'merge-base','--is-ancestor',r.commit_id_initiating,r.correction_id],capture_output=True,timeout=30)
    if m.returncode==0: out['ancestry_status']='confirmed_within_1000_depth'
    else:
      shallow=subprocess.run(['git','-C',str(td),'rev-parse','--is-shallow-repository'],capture_output=True,text=True).stdout.strip()
      out['ancestry_status']='not_ancestor_in_fetched_graph' if shallow=='false' else 'not_demonstrated_within_1000_depth'
    return out
  except Exception as ex:
    out['ancestry_status']='error'; out['error']=repr(ex); return out
  finally: shutil.rmtree(td,ignore_errors=True)

out=[]
with ThreadPoolExecutor(max_workers=8) as pool:
  fs=[pool.submit(check,r) for _,r in rows.iterrows()]
  for n,f in enumerate(as_completed(fs),1):
    out.append(f.result())
    if n%10==0: print(f'checked {n}/{len(rows)}',flush=True)
a=pd.DataFrame(out)
a.to_csv(base/'path_validation_ancestry_results.csv',index=False)
print(a.ancestry_status.value_counts(dropna=False).to_string())
