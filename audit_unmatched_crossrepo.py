"""Audit each unmatched event row against all correction rows with the same hash.

Usage:
  python audit_unmatched_crossrepo.py --archive-root PATH --out PATH
"""
import argparse
from pathlib import Path
import pandas as pd


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive-root',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    a=ap.parse_args()
    base=a.archive_root
    events=pd.read_excel(base/'labs/depth_intro_correction_classified.xlsx')
    candidates=pd.read_excel(base/'labs/INTRO_COMMIT_REASON4_CORRECTIONS.xlsx')
    events=events.loc[events.correction_id.notna()].copy()
    events['event_source_row']=events.index+2
    exact=events.merge(candidates,left_on=['repo_id','correction_id','old_path'],
                       right_on=['repo_id','commit_id','old_path'],how='left',indicator=True,
                       suffixes=('_event','_candidate'))
    unmatched=exact.loc[exact['_merge'].eq('left_only'),
                        ['event_source_row','repo_id','old_path','correction_id']].copy()
    unmatched=unmatched.rename(columns={'repo_id':'event_repo_id','old_path':'event_old_path'})
    candidate_index={}
    named_candidates=candidates.loc[candidates.repo_id.notna() & candidates.commit_id.notna()].copy()
    named_candidates['repo_id']=named_candidates.repo_id.astype(str)
    for sha,grp in named_candidates.groupby('commit_id',dropna=True):
        candidate_index[str(sha)]=grp[['repo_id','old_path']].drop_duplicates().to_dict('records')
    out=[]
    for row in unmatched.itertuples(index=False):
        matches=candidate_index.get(str(row.correction_id),[])
        cross=[m for m in matches if str(m['repo_id']) != str(row.event_repo_id)]
        same_path=[m for m in cross if str(m['old_path']) == str(row.event_old_path)]
        out.append({
          'event_source_row':row.event_source_row,
          'event_repo_id':row.event_repo_id,
          'event_old_path':row.event_old_path,
          'correction_id':row.correction_id,
          'candidate_records_for_hash':len(matches),
          'candidate_repo_ids_for_hash':' | '.join(sorted({str(m['repo_id']) for m in matches})),
          'candidate_old_paths_for_hash':' | '.join(sorted({str(m['old_path']) for m in matches})),
          'cross_repository_hash_record':bool(cross),
          'same_old_path_cross_repository_record':bool(same_path),
          'cross_repository_repo_ids':' | '.join(sorted({str(m['repo_id']) for m in cross})),
          'same_old_path_cross_repository_repo_ids':' | '.join(sorted({str(m['repo_id']) for m in same_path})),
        })
    result=pd.DataFrame(out)
    a.out.parent.mkdir(parents=True,exist_ok=True); result.to_csv(a.out,index=False)
    print('Unmatched event rows, direct left-only count:',len(result))
    print('Distinct unmatched event keys:',result[['event_repo_id','correction_id','event_old_path']].drop_duplicates().shape[0])
    print('Distinct unmatched hashes:',result.correction_id.nunique())
    cross=result[result.cross_repository_hash_record]
    print('Cross-repository hashes:',cross.correction_id.nunique())
    print('Cross-repository event keys:',cross[['event_repo_id','correction_id','event_old_path']].drop_duplicates().shape[0])
    print('Same-old-path cross-repository event keys:',result.loc[result.same_old_path_cross_repository_record,['event_repo_id','correction_id','event_old_path']].drop_duplicates().shape[0])
    print('Wrote',a.out)

if __name__=='__main__': main()
