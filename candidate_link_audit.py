"""Reproduce the descriptive candidate-link audit reported in the short paper.

Usage:
  python candidate_link_audit.py --events PATH --candidates PATH --out PATH

Inputs are the v1 Zenodo archive workbooks:
  depth_intro_correction_classified.xlsx
  INTRO_COMMIT_REASON4_CORRECTIONS.xlsx

The script reports reconciliation counts and descriptive intervals only. It does
not label candidates as true reversals or reconstruct repository tree states.
"""
import argparse
from pathlib import Path
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--events', required=True, type=Path)
    parser.add_argument('--candidates', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()

    events = pd.read_excel(args.events)
    candidates = pd.read_excel(args.candidates)
    required_event = {'repo_id', 'old_path', 'commit_id', 'commit_time', 'commit_index', 'correction_id'}
    required_candidate = {'repo_id', 'old_path', 'commit_id', 'commit_time', 'commit_index'}
    if not required_event.issubset(events.columns):
        raise ValueError(f'Event workbook missing columns: {sorted(required_event - set(events.columns))}')
    if not required_candidate.issubset(candidates.columns):
        raise ValueError(f'Candidate workbook missing columns: {sorted(required_candidate - set(candidates.columns))}')

    candidate_rows = events.loc[events['correction_id'].notna()].copy()
    matched = candidate_rows.merge(
        candidates,
        left_on=['repo_id', 'correction_id', 'old_path'],
        right_on=['repo_id', 'commit_id', 'old_path'],
        how='left',
        suffixes=('_initiating', '_candidate'),
        indicator=True,
    )
    exact = matched.loc[matched['_merge'].eq('both')].copy()
    unmatched = matched.loc[matched['_merge'].eq('left_only')].copy()
    later_mask = exact['commit_index_candidate'] > exact['commit_index_initiating']
    later = exact.loc[later_mask].copy()
    elapsed_ties = int((later['commit_time_candidate'] == later['commit_time_initiating']).sum())
    earlier = int((exact['commit_index_candidate'] < exact['commit_index_initiating']).sum())

    event_key = ['repo_id', 'commit_id_initiating', 'old_path']
    earliest = (later.sort_values(['commit_index_candidate', 'commit_time_candidate'])
                .drop_duplicates(event_key, keep='first').copy())
    earliest['elapsed_days'] = (
        earliest['commit_time_candidate'] - earliest['commit_time_initiating']
    ) / 86400

    rows = [
        ('Initiating event-path rows', len(events), 'All rows in classified event workbook'),
        ('Unique initiating commits', events['commit_id'].nunique(), 'Distinct initiating commit identifiers'),
        ('Unique initiating repositories', events['repo_id'].nunique(), 'Distinct repository identifiers'),
        ('Rows with candidate correction ID', len(candidate_rows), 'Candidate identifier present'),
        ('Rows without candidate correction ID', int(events['correction_id'].isna().sum()), 'Candidate identifier missing'),
        ('Exact repository-path-commit matches', len(exact), 'Candidate matched to correction export'),
        ('Candidate IDs without exact match', int(matched['_merge'].eq('left_only').sum()), 'Direct count of left-only candidate rows'),
        ('Distinct unmatched event keys', unmatched[['repo_id', 'correction_id', 'old_path']].drop_duplicates().shape[0], 'Unique repository-candidate-hash-path combinations'),
        ('Distinct unmatched correction hashes', unmatched['correction_id'].nunique(), 'Unique hashes among directly unmatched rows'),
        ('Chronologically earlier exact matches', earlier, 'Candidate commit index precedes initiating event'),
        ('Chronologically later exact matches', len(later), 'Candidate commit index follows initiating event'),
        ('Later matches with tied timestamps', elapsed_ties, 'Commit index later but elapsed time is zero'),
        ('Earliest later candidate per event-path', len(earliest), 'After event-path deduplication'),
        ('Distinct initiating commit hashes with retained links', earliest['commit_id_initiating'].nunique(), 'Distinct SHA-1 hashes, repository not included'),
        ('Repository-commit pairs with retained links', earliest[['repo_id', 'commit_id_initiating']].drop_duplicates().shape[0], 'Repository-scoped initiating commits'),
        ('Repositories with retained links', earliest['repo_id'].nunique(), 'Distinct repository identifiers'),
        ('Hashes repeated across repository IDs', int((earliest.groupby('commit_id_initiating')['repo_id'].nunique() > 1).sum()), 'Distinct hashes found in multiple repository IDs'),
        ('Rows carrying a repeated hash', int(earliest['commit_id_initiating'].isin(earliest.groupby('commit_id_initiating')['repo_id'].nunique().loc[lambda x: x > 1].index).sum()), 'Repository-link rows sharing a hash across repositories'),
        ('Median elapsed days', earliest['elapsed_days'].median(), 'Candidate-link interval, not reversal latency'),
        ('First quartile elapsed days', earliest['elapsed_days'].quantile(.25), 'Candidate-link interval'),
        ('Third quartile elapsed days', earliest['elapsed_days'].quantile(.75), 'Candidate-link interval'),
        ('Mean elapsed days', earliest['elapsed_days'].mean(), 'Candidate-link interval'),
        ('Maximum elapsed days', earliest['elapsed_days'].max(), 'Candidate-link interval'),
        ('correction_diff <= 0', int((earliest['correction_diff'] <= 0).sum()), 'Repository maximum-depth-change sum'),
        ('correction_diff == 0', int((earliest['correction_diff'] == 0).sum()), 'Repository maximum-depth-change sum'),
        ('correction_diff > 0', int((earliest['correction_diff'] > 0).sum()), 'Repository maximum-depth-change sum'),
    ]
    out = pd.DataFrame(rows, columns=['metric', 'value', 'definition'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    print(out.to_string(index=False))
    print(f'\nWrote {args.out}')

if __name__ == '__main__':
    main()
