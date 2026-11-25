"""Merge the preserved complete-history ancestry run with a fresh path-tree follow-up.

Usage: python merge_earlier_link_checks.py --archive-root PATH --initial-results CSV --followup-results CSV --out CSV
"""
import argparse
from pathlib import Path
import pandas as pd

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--archive-root',type=Path,required=True)
p.add_argument('--initial-results',type=Path,required=True)
p.add_argument('--followup-results',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
base=pd.read_csv(a.initial_results)
fresh=pd.read_csv(a.followup_results)
key=['repo_id','initiating_sha','candidate_sha']
pathcols=[c for c in ['target_path','candidate_parent_target_present','candidate_target_present','event_parent_target_present','event_target_present','reintroduced_at_initiating_event'] if c in fresh]
base=base.merge(fresh[key+pathcols],on=key,how='left',suffixes=('','_followup'))
base['path_tree_check_status']=base.reintroduced_at_initiating_event.map(lambda x:'confirmed from current Git trees' if str(x).lower()=='true' else 'not retrievable in follow-up run')
e=pd.read_excel(a.archive_root/'labs/depth_intro_correction_classified.xlsx')
c=pd.read_excel(a.archive_root/'labs/INTRO_COMMIT_REASON4_CORRECTIONS.xlsx')
x=e.loc[e.correction_id.notna()].merge(c,left_on=['repo_id','correction_id','old_path'],right_on=['repo_id','commit_id','old_path'],suffixes=('_event','_candidate'))
x=x.loc[x.commit_index_candidate<x.commit_index_event,['repo_id','commit_id_event','correction_id','old_path','action']]
x=x.rename(columns={'commit_id_event':'initiating_sha','correction_id':'candidate_sha','old_path':'archive_target_path','action':'archive_candidate_action'})
base=base.merge(x,on=key,how='left')
a.out.parent.mkdir(parents=True,exist_ok=True); base.to_csv(a.out,index=False)
print('Earlier links:',len(base))
print('Candidate is ancestor of event:',int(((base.candidate_descendant=='no')&(base.event_descendant=='yes')).sum()))
print('Archived action is deletion:',int(base.archive_candidate_action.astype(str).str.lower().eq('delete').sum()))
print('Path tree deletion/reintroduction confirmed:',int(base.reintroduced_at_initiating_event.fillna(False).astype(bool).sum()))
print('Wrote',a.out)
