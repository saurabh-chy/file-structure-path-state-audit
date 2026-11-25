"""Check Git ancestry for exact candidate links earlier than their events.

Usage:
  python check_earlier_link_ancestry.py --archive-root PATH --out PATH
"""
import argparse
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive-root', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--workers', type=int, default=8)
    args = ap.parse_args()
    base = args.archive_root
    events = pd.read_excel(base/'labs/depth_intro_correction_classified.xlsx')
    candidates = pd.read_excel(base/'labs/INTRO_COMMIT_REASON4_CORRECTIONS.xlsx')
    repo_data = pd.read_csv(base/'datasets/github_data_07_03_2024.csv', low_memory=False)
    repo_data['repo_key'] = (repo_data['owner.name'].astype(str)+'_'+repo_data['name'].astype(str)).str.lower()
    repo_data = repo_data.drop_duplicates('repo_key').set_index('repo_key')
    exact = events.loc[events.correction_id.notna()].merge(
        candidates, left_on=['repo_id','correction_id','old_path'],
        right_on=['repo_id','commit_id','old_path'], suffixes=('_event','_candidate'))
    earlier = exact.loc[exact.commit_index_candidate < exact.commit_index_event].copy()
    earlier['repo_key'] = earlier.repo_id.str.lower()
    earlier['url'] = earlier.repo_key.map(repo_data.url)
    earlier['clone_url'] = earlier.repo_key.map(repo_data.clone_url)
    print('Earlier exact links:', len(earlier), 'unique repository-event-candidate triples:',
          earlier[['repo_id','commit_id_event','correction_id']].drop_duplicates().shape[0], flush=True)

    def check(row):
        work = Path(tempfile.mkdtemp(prefix='earlier-link-check-'))
        result = {'repo_id':row.repo_id,'initiating_sha':row.commit_id_event,
                  'candidate_sha':row.correction_id,'commit_index_event':int(row.commit_index_event),
                  'commit_index_candidate':int(row.commit_index_candidate),'repo_url':row.url,
                  'target_path':row.old_path,'archive_candidate_action':row.action,
                  'initial_fetch':'','candidate_descendant':'','event_descendant':'','status':''}
        try:
            subprocess.run(['git','init','-q',str(work)],check=True)
            subprocess.run(['git','-C',str(work),'remote','add','origin',row.clone_url],check=True)
            fetch=subprocess.run(['git','-C',str(work),'-c','protocol.version=2','fetch','--quiet',
                                  '--depth=1','--filter=blob:none','origin',row.commit_id_event,row.correction_id],
                                 capture_output=True,timeout=180)
            if fetch.returncode:
                result['status']='initial_fetch_failed'; result['initial_fetch']=fetch.stderr.decode(errors='replace')[:500]
                return result
            fetch=subprocess.run(['git','-C',str(work),'-c','protocol.version=2','fetch','--quiet',
                                  '--deepen=10000','--filter=tree:0','origin',row.commit_id_event],
                                 capture_output=True,timeout=600)
            if fetch.returncode:
                result['status']='deepen_failed'; result['initial_fetch']=fetch.stderr.decode(errors='replace')[:500]
                return result
            cdesc=subprocess.run(['git','-C',str(work),'merge-base','--is-ancestor',row.commit_id_event,row.correction_id])
            edesc=subprocess.run(['git','-C',str(work),'merge-base','--is-ancestor',row.correction_id,row.commit_id_event])
            result['candidate_descendant']='yes' if cdesc.returncode==0 else 'no'
            result['event_descendant']='yes' if edesc.returncode==0 else 'no'
            def has_path(rev):
                q=subprocess.run(['git','-C',str(work),'cat-file','-e',f'{rev}:{row.old_path}'],capture_output=True)
                return 'yes' if q.returncode==0 else 'no'
            cparent=subprocess.run(['git','-C',str(work),'rev-parse',f'{row.correction_id}^1'],capture_output=True,text=True)
            eparent=subprocess.run(['git','-C',str(work),'rev-parse',f'{row.commit_id_event}^1'],capture_output=True,text=True)
            result['candidate_parent_target_present']=has_path(cparent.stdout.strip()) if cparent.returncode==0 else 'no_parent'
            result['candidate_target_present']=has_path(row.correction_id)
            result['event_parent_target_present']=has_path(eparent.stdout.strip()) if eparent.returncode==0 else 'no_parent'
            result['event_target_present']=has_path(row.commit_id_event)
            result['reintroduced_at_initiating_event']=(result['candidate_parent_target_present']=='yes' and result['candidate_target_present']=='no' and result['event_parent_target_present']=='no' and result['event_target_present']=='yes')
            shallow=subprocess.run(['git','-C',str(work),'rev-parse','--is-shallow-repository'],capture_output=True,text=True).stdout.strip()
            result['status']='checked_with_shallow_boundary' if shallow=='true' else 'checked_complete_history'
        except Exception as exc:
            result['status']='error:'+repr(exc)
        finally:
            shutil.rmtree(work,ignore_errors=True)
        return result

    results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(check,row) for _,row in earlier.iterrows()]
        for future in as_completed(futures):
            results.append(future.result())
    out=pd.DataFrame(results).sort_values(['repo_id','initiating_sha','candidate_sha'])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(args.out,index=False)
    print(out.status.value_counts(dropna=False).to_string())
    print('Wrote',args.out)

if __name__=='__main__':
    main()
