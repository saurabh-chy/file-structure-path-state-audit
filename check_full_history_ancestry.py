"""Fetch complete history for candidates unresolved after deepening and test ancestry.

Usage:
  python check_full_history_ancestry.py --work-dir PATH [--out PATH]

The script reads the census frame and deep-ancestry output, then writes
path_validation_ancestry_full_history_results.csv in work-dir by default.
"""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path
import pandas as pd


def run(cmd, timeout=600):
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-dir',required=True,type=Path)
    p.add_argument('--out',type=Path)
    a=p.parse_args(); d=a.work_dir
    frame=pd.read_csv(d/'path_validation_sample_frame.csv')
    deep=pd.read_csv(d/'path_validation_ancestry_deep_results.csv')
    # Only retry cases still unconfirmed or unresolved after the configured deepening.
    pending=deep.loc[~deep.ancestry_status_deep.fillna('').str.startswith('confirmed')].copy()
    pending=pending.merge(frame[['sample_order','repo_id','url','commit_id_initiating','commit_id_candidate']],on=['sample_order','repo_id'],how='left')
    pending=pending.rename(columns={'commit_id_initiating':'initiating_sha','commit_id_candidate':'candidate_sha'})
    results=[]
    for row in pending.itertuples(index=False):
        work=Path(tempfile.mkdtemp(prefix='full-history-ancestry-'))
        repo_url=str(row.url).rstrip('/')+'.git'
        rec={'sample_order':int(row.sample_order),'repo_id':row.repo_id,
             'initiating_sha':row.initiating_sha,'candidate_sha':row.candidate_sha,
             'repository_url':str(row.url),'fetch_status':'','history_complete':False,
             'candidate_descendant':'','event_descendant':'','ancestry_status_full_history':''}
        try:
            r=run(['git','init','-q',str(work)])
            if r.returncode: raise RuntimeError(r.stderr.strip())
            r=run(['git','-C',str(work),'remote','add','origin',repo_url])
            if r.returncode: raise RuntimeError(r.stderr.strip())
            r=run(['git','-C',str(work),'-c','protocol.version=2','fetch','--quiet','--depth=1','--filter=blob:none','origin',str(row.initiating_sha),str(row.candidate_sha)],timeout=300)
            if r.returncode:
                rec['fetch_status']='commit_fetch_failed'; rec['ancestry_status_full_history']='unavailable'; rec['error']=r.stderr.strip()[:800]
            else:
                r=run(['git','-C',str(work),'-c','protocol.version=2','fetch','--quiet','--unshallow','--filter=tree:0','origin'],timeout=1800)
                if r.returncode:
                    # Some servers reject --unshallow on repositories that were already completed.
                    shallow=run(['git','-C',str(work),'rev-parse','--is-shallow-repository'])
                    if shallow.stdout.strip()!='false':
                        rec['fetch_status']='full_history_fetch_failed'; rec['ancestry_status_full_history']='unavailable'; rec['error']=r.stderr.strip()[:800]
                    else:
                        rec['fetch_status']='retrieved'
                else: rec['fetch_status']='retrieved'
                if rec['fetch_status']=='retrieved':
                    shallow=run(['git','-C',str(work),'rev-parse','--is-shallow-repository'])
                    rec['history_complete']=shallow.stdout.strip()=='false'
                    anc=run(['git','-C',str(work),'merge-base','--is-ancestor',str(row.initiating_sha),str(row.candidate_sha)])
                    rev=run(['git','-C',str(work),'merge-base','--is-ancestor',str(row.candidate_sha),str(row.initiating_sha)])
                    rec['candidate_descendant']='yes' if anc.returncode==0 else 'no'
                    rec['event_descendant']='yes' if rev.returncode==0 else 'no'
                    rec['ancestry_status_full_history']='confirmed_after_full_history' if anc.returncode==0 and rec['history_complete'] else 'not_confirmed_after_full_history'
        except Exception as e:
            rec['fetch_status']='error'; rec['ancestry_status_full_history']='unavailable'; rec['error']=repr(e)
        finally:
            shutil.rmtree(work,ignore_errors=True)
        results.append(rec)
        print(row.repo_id,rec['fetch_status'],rec['ancestry_status_full_history'],flush=True)
    out=pd.DataFrame(results)
    dest=a.out or d/'path_validation_ancestry_full_history_results.csv'
    dest.parent.mkdir(parents=True,exist_ok=True); out.to_csv(dest,index=False)
    print('Full-history checks:',len(out),'confirmed:',int(out.ancestry_status_full_history.fillna('').str.startswith('confirmed').sum()))
    print('Wrote',dest)

if __name__=='__main__': main()
