"""Join Git-tree, ancestry, and move-destination checks into one audit table.

Usage: python finalize_path_validation.py --work-dir ./audit-output
Expected inputs in work-dir: path_validation_sample_frame.csv,
path_validation_sample_results.csv, path_validation_ancestry_results.csv,
optional path_validation_ancestry_deep_results.csv, and
path_validation_move_destination_results.csv.
"""
import argparse
from pathlib import Path
import pandas as pd

p=argparse.ArgumentParser()
p.add_argument('--work-dir',required=True,type=Path)
a=p.parse_args(); d=a.work_dir
frame=pd.read_csv(d/'path_validation_sample_frame.csv')
git=pd.read_csv(d/'path_validation_sample_results.csv')
anc=pd.read_csv(d/'path_validation_ancestry_results.csv')
move=pd.read_csv(d/'path_validation_move_destination_results.csv') if (d/'path_validation_move_destination_results.csv').exists() else pd.DataFrame()
final=frame.merge(git,on=['sample_order','repo_id'],how='left',suffixes=('','_git'))
if 'ancestry_status' in anc:
 final=final.merge(anc[['sample_order','repo_id','ancestry_status']],on=['sample_order','repo_id'],how='left')
if (d/'path_validation_ancestry_deep_results.csv').exists():
 deep=pd.read_csv(d/'path_validation_ancestry_deep_results.csv')
 if 'ancestry_status_deep' in deep:
  final=final.merge(deep[['sample_order','repo_id','ancestry_status_deep']],on=['sample_order','repo_id'],how='left')
if (d/'path_validation_ancestry_full_history_results.csv').exists():
 full=pd.read_csv(d/'path_validation_ancestry_full_history_results.csv')
 final=final.merge(full[['sample_order','repo_id','ancestry_status_full_history']],on=['sample_order','repo_id'],how='left')
if len(move):
 keep=[c for c in ['sample_order','repo_id','event_parent_destination_present','event_destination_present','candidate_destination_present','status'] if c in move]
 mv=move[keep].copy()
 mv=mv.rename(columns={'status':'move_destination_status','candidate_destination_present':'move_candidate_destination_present'})
 final=final.merge(mv,on=['sample_order','repo_id'],how='left')
final['ancestry_confirmed']=final.get('ancestry_status',pd.Series('',index=final.index)).fillna('').str.startswith('confirmed')
if 'ancestry_status_deep' in final:
 final['ancestry_confirmed'] |= final.ancestry_status_deep.fillna('').str.startswith('confirmed')
if 'ancestry_status_full_history' in final:
 final['ancestry_confirmed'] |= final.ancestry_status_full_history.fillna('').str.startswith('confirmed')
# Preserve the observed Git facts independently from the archive's semantic labels.
final['record_path_state_fidelity']=(final.fetch_status.eq('retrieved') & final.event_parent_present.eq(False) & final.target_present_event.eq(True) & final.path_removed_after_candidate.eq(True))
base_restore=final.record_path_state_fidelity & final.ancestry_confirmed
move_rows=final.action.astype(str).str.lower().eq('move')
move_dest_ok=(final.get('event_parent_destination_present',pd.Series(False,index=final.index)).eq(True) & final.get('event_destination_present',pd.Series(True,index=final.index)).eq(False) & final.get('move_candidate_destination_present',pd.Series(False,index=final.index)).eq(True))
final['strict_path_state_restoration']=base_restore & (~move_rows | move_dest_ok)
final['days_to_candidate']=(pd.to_numeric(final.commit_time_candidate,errors='coerce')-pd.to_numeric(final.commit_time_initiating,errors='coerce'))/86400
final.to_csv(d/'path_validation_final.csv',index=False)
print('Git histories retrievable:',int(final.fetch_status.eq('retrieved').sum()),'/',len(final))
print('Path-state record fidelity:',int(final.record_path_state_fidelity.sum()),'/',int(final.fetch_status.eq('retrieved').sum()))
print('Ancestry confirmed:',int(final.ancestry_confirmed.sum()),'/',int(final.fetch_status.eq('retrieved').sum()))
print('Strict restorations:',int(final.strict_path_state_restoration.sum()))
print('Action mix among retrievable:',final.loc[final.fetch_status.eq('retrieved'),'action'].value_counts(dropna=False).to_dict())
print('Wrote',d/'path_validation_final.csv')
