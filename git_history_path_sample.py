"""Retrieve commit and tree-state evidence for a seeded sample of candidate links.

This is an automated path-state screen, not a semantic reversal label or a
substitute for independent human coding. It fetches only selected commits and
first parents with blob filtering, rather than cloning full repository history.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import pandas as pd
import subprocess, tempfile, shutil, json

parser = argparse.ArgumentParser()
parser.add_argument('--archive-root', required=True, type=Path, help='Extracted Zenodo v1 archive root')
parser.add_argument('--out-dir', required=True, type=Path, help='Directory for sample frame and tree-state outputs')
parser.add_argument('--seed', type=int, default=20261125)
parser.add_argument('--sample-size', type=int, default=100)
args = parser.parse_args()
BASE = args.archive_root
OUT = args.out_dir
OUT.mkdir(parents=True, exist_ok=True)
SEED = args.seed
N_SAMPLE = args.sample_size

events = pd.read_excel(BASE/'labs/depth_intro_correction_classified.xlsx')
candidates = pd.read_excel(BASE/'labs/INTRO_COMMIT_REASON4_CORRECTIONS.xlsx')
links = events.loc[events.correction_id.notna()].merge(
    candidates,
    left_on=['repo_id','correction_id','old_path'],
    right_on=['repo_id','commit_id','old_path'],
    suffixes=('_initiating','_candidate'))
links = links.loc[links.commit_index_candidate > links.commit_index_initiating]
links = (links.sort_values(['commit_index_candidate','commit_time_candidate'])
         .drop_duplicates(['repo_id','commit_id_initiating','old_path']))
repos = pd.read_csv(BASE/'datasets/github_data_07_03_2024.csv', low_memory=False)
repos['repo_key'] = (repos['owner.name'].astype(str) + '_' + repos['name'].astype(str)).str.lower()
links['repo_key_lower'] = links['repo_id'].astype(str).str.lower()
links = links.merge(repos[['repo_key','url','clone_url']], left_on='repo_key_lower', right_on='repo_key', how='left')
eligible = links.loc[links.clone_url.notna()].copy()
sample = eligible.sample(n=min(N_SAMPLE, len(eligible)), random_state=SEED).reset_index(drop=True)
sample.insert(0, 'sample_order', range(1, len(sample)+1))
sample.to_csv(OUT/'path_validation_sample_frame.csv', index=False)


def run_git(repo_dir, *args, timeout=180):
    return subprocess.run(['git','-C',str(repo_dir),*map(str,args)],capture_output=True,timeout=timeout)

def commit_parent(repo_dir, sha):
    r=run_git(repo_dir,'cat-file','-p',sha)
    if r.returncode: return None
    for line in r.stdout.splitlines():
        if line.startswith(b'parent '): return line.split()[1].decode()
    return None

def tree_paths(repo_dir, sha):
    r=run_git(repo_dir,'ls-tree','-r','-z','--name-only',sha,timeout=180)
    if r.returncode: return None
    return {p.decode('utf-8','surrogateescape') for p in r.stdout.split(b'\0') if p}

def audit(row):
    rec={
      'sample_order':int(row.sample_order),'repo_id':row.repo_id,'repo_url':row.url,
      'initiating_sha':row.commit_id_initiating,'candidate_sha':row.correction_id,
      'target_path':row.old_path,'candidate_action':row.action if pd.notna(row.action) else '',
      'candidate_new_path':row.new_path if pd.notna(row.new_path) else '',
      'initiating_message':str(row.message_initiating)[:500] if pd.notna(row.message_initiating) else '',
      'candidate_message':str(row.message_candidate)[:500] if pd.notna(row.message_candidate) else '',
      'fetch_status':'','event_parent_present':'','target_present_event':'',
      'target_present_candidate_parent':'','target_present_candidate':'',
      'candidate_destination_present':'','path_removed_after_candidate':'',
      'candidate_outcome':'','error':''}
    td=Path(tempfile.mkdtemp(prefix='path-audit-'))
    try:
      subprocess.run(['git','init','-q',str(td)],check=True,timeout=20)
      subprocess.run(['git','-C',str(td),'remote','add','origin',row.clone_url],check=True,timeout=20)
      shas=[row.commit_id_initiating,row.correction_id]
      f=run_git(td,'-c','protocol.version=2','fetch','--quiet','--depth=1','--filter=blob:none','origin',*shas,timeout=180)
      if f.returncode:
        rec['fetch_status']='unavailable'; rec['error']=f.stderr.decode('utf8','replace')[-1500:]; return rec
      ep=commit_parent(td,row.commit_id_initiating)
      cp=commit_parent(td,row.correction_id)
      if not ep or not cp:
        rec['fetch_status']='root_or_parent_unavailable'; return rec
      parents=list(dict.fromkeys([ep,cp]))
      f=run_git(td,'-c','protocol.version=2','fetch','--quiet','--depth=1','--filter=blob:none','origin',*parents,timeout=180)
      if f.returncode:
        rec['fetch_status']='parent_unavailable'; rec['error']=f.stderr.decode('utf8','replace')[-1500:]; return rec
      pre=tree_paths(td,ep); post_event=tree_paths(td,row.commit_id_initiating)
      pre_candidate=tree_paths(td,cp); post_candidate=tree_paths(td,row.correction_id)
      if any(x is None for x in [pre,post_event,pre_candidate,post_candidate]):
        rec['fetch_status']='tree_unavailable'; return rec
      target=str(row.old_path)
      dest=str(row.new_path) if pd.notna(row.new_path) else ''
      rec.update(fetch_status='retrieved',
        event_parent_present=target in pre,
        target_present_event=target in post_event,
        target_present_candidate_parent=target in pre_candidate,
        target_present_candidate=target in post_candidate,
        candidate_destination_present=bool(dest and dest in post_candidate),
        path_removed_after_candidate=target in post_event and target not in post_candidate)
      removed=bool(target in post_event and target not in post_candidate)
      dest_ok=bool(dest and dest in post_candidate and dest.count('/')<target.count('/'))
      if not target in post_event:
        status='target_absent_at_initiating_commit'
      elif removed and dest_ok:
        status='deep_path_removed_shallower_destination_present'
      elif removed:
        status='deep_path_removed_no_shallower_destination'
      elif target in post_candidate:
        status='deep_path_still_present_after_candidate'
      else:
        status='other_path_state'
      rec['candidate_outcome']=status
      return rec
    except Exception as exc:
      rec['fetch_status']='error'; rec['error']=repr(exc); return rec
    finally:
      shutil.rmtree(td,ignore_errors=True)

results=[]
with ThreadPoolExecutor(max_workers=8) as pool:
    futs=[pool.submit(audit,row) for _,row in sample.iterrows()]
    for j,f in enumerate(as_completed(futs),1):
      r=f.result(); results.append(r)
      if j%10==0: print(f'completed {j}/{len(sample)}',flush=True)
result=pd.DataFrame(results).sort_values('sample_order')
result.to_csv(OUT/'path_validation_sample_results.csv',index=False)
# Prepare blinded-ish coding sheet, leaving human decisions blank.
coding=result.copy()
coding['coder_1_label']=''
coding['coder_2_label']=''
coding['adjudicated_label']=''
coding['coder_notes']=''
coding.to_csv(OUT/'path_validation_coding_sheet.csv',index=False)
print('\nSTATUS COUNTS')
print(result.fetch_status.value_counts(dropna=False).to_string())
print('\nPATH OUTCOME COUNTS (retrieved only)')
print(result.loc[result.fetch_status.eq('retrieved'),'candidate_outcome'].value_counts(dropna=False).to_string())
print('\nWROTE path_validation_sample_frame.csv, path_validation_sample_results.csv, path_validation_coding_sheet.csv')
