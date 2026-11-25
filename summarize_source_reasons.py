"""Summarize archive-provided reason labels for Git-retrieved census links.

Usage: python summarize_source_reasons.py --final path_validation_census/path_validation_final.csv --out source_reason_descriptive_results.csv
"""
import argparse
from pathlib import Path
import pandas as pd

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--final',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
df=pd.read_csv(a.final)
df=df.loc[df.fetch_status.eq('retrieved')].copy()
df['days_to_candidate']=pd.to_numeric(df.days_to_candidate,errors='coerce')
rows=[]
for reason,g in df.groupby('Reason 1_initiating',dropna=False):
    gdays=g.days_to_candidate.dropna()
    rows.append({'coverage':'Git-retrieved census links','n_retrieved':len(df),
                 'source_reason':'(missing)' if pd.isna(reason) else reason,
                 'label_n':len(g),'median_days_to_candidate':gdays.median(),
                 'within_30_days_n':int(gdays.le(30).sum()),
                 'strict_path_presence_returns_n':int(g.strict_path_state_restoration.sum()),
                 'strict_path_presence_returns_pct':100*g.strict_path_state_restoration.mean()})
out=pd.DataFrame(rows).sort_values('source_reason')
a.out.parent.mkdir(parents=True,exist_ok=True); out.to_csv(a.out,index=False)
print(out.to_string(index=False)); print('Wrote',a.out)
