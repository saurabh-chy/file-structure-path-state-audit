# Git-history audit of candidate file-structure corrections

## Scope

This package audits version 1 of the GitHub file-structure archive (Zenodo DOI: https://doi.org/10.5281/zenodo.20601252). It evaluates the fidelity and temporal ordering of released candidate-link records for downstream reuse. It does not assess the source article's selected case examples or treat the archive fields as a validated measure of developer-intended corrections.

## Main results

- The event workbook contains 1,167 initiating event-path rows; 708 have a correction identifier.
- Exact repository-path-commit matching yields 566 records. A direct left-only count identifies 142 unmatched event rows, with 129 distinct event keys and 107 distinct candidate hashes.
- Keeping the earliest later candidate yields 526 repository-commit-path links across 526 repository IDs and 514 distinct initiating hashes. Eleven hashes recur across repository IDs, accounting for 23 link rows.
- An initial URL join in the audit was case-sensitive and resolved 300 links. Lowercasing both repository keys resolves all 526 URLs.
- Git histories were retrieved for 509 links. All 509 match the recorded path sequence and have confirmed candidate ancestry; 17 histories or required parents were unavailable.
- Among retrieved links, the archive records 447 deletions and 62 moves. Seven moves returned to a destination that existed before and disappeared at the initiating commit. The strict path-presence return count is 454/509 (89.2%; Wilson 95% CI [86.2%, 91.6%]). Candidate construction selects operations on the same deep path, so this is a record-consistency check, not a reversal-validity or developer-intent estimate.
- Of ten exact candidate links that precede their initiating events, all ten are ancestry-confirmed as earlier deletions. A follow-up tree-state check confirms deletion and reintroduction for six; four path checks were unavailable in that follow-up. These indicate apparent path reintroductions in the archive's sequence.
- Among the 509 Git-retrieved links, source-provided Vendor and Resource labels account for 318. All four Error-labelled links and 22 of 33 Generated-labelled links were followed within 30 days. Strict path-presence returns were less common for Normal-labelled links (68/91, 74.7%) than for Vendor-labelled links (196/204, 96.1%); Normal-labelled links included 23 moves compared with 10 for Vendor. These descriptive patterns reflect a different operation mix; source labels describe path introduction and have not been independently validated as explanations for later removals.
- No independent semantic coding was conducted for this note. Coding the meaning and scope of removals is future work; no coder sample or coding workbooks are included.

## Package contents

- Workbook reconciliation: `candidate_link_audit.py`, `candidate_link_audit_summary.csv`.
- Unmatched-row audit: `audit_unmatched_crossrepo.py`, `unmatched_candidate_hash_crossrepo_audit.csv`. The output preserves one row per unmatched event row.
- Git census and validation scripts: `git_history_path_sample.py`, `check_sample_ancestry.py`, `deepen_sample_ancestry.py`, `check_full_history_ancestry.py`, `check_move_destinations.py`, and `finalize_path_validation.py`.
- Source-label summary: `summarize_source_reasons.py`, `source_reason_descriptive_results.csv` (509 retrieved histories).
- Earlier-link checks: `check_earlier_link_ancestry.py`, `merge_earlier_link_checks.py`, and three `earlier_link_*.csv` outputs. `earlier_link_git_ancestry.csv` is the final merged and authoritative output. `earlier_link_path_tree_followup.csv` is an intermediate input to the merge; it is retained to reproduce that output. The initial full-history ancestry output is retained separately.
- `partial_correction_reason_labels.csv`: sparse archive `Correction Reason` counts across the 526 retained links.
- `path_validation_census/`: the 526-link frame, tree-state results, ancestry outputs including the full-history retry, move-destination checks, and finalized audit CSV. The coding sheet is excluded because no semantic coding was conducted.

## Reproduction

Requirements: Python 3, pandas, openpyxl, and Git. Download and extract the Zenodo v1 archive before running the workbook and history scripts. The original archive is not redistributed in this package.

```bash
python candidate_link_audit.py \
  --events /path/to/Thesis-FileStructureAnalysis-main/labs/depth_intro_correction_classified.xlsx \
  --candidates /path/to/Thesis-FileStructureAnalysis-main/labs/INTRO_COMMIT_REASON4_CORRECTIONS.xlsx \
  --out candidate_link_audit_summary.csv

python audit_unmatched_crossrepo.py \
  --archive-root /path/to/Thesis-FileStructureAnalysis-main \
  --out unmatched_candidate_hash_crossrepo_audit.csv
```

To reproduce the Git-tree census and classifications:

```bash
python git_history_path_sample.py \
  --archive-root /path/to/Thesis-FileStructureAnalysis-main \
  --out-dir ./path_validation_census \
  --seed 20261125 --sample-size 526
python check_sample_ancestry.py --work-dir ./path_validation_census
python deepen_sample_ancestry.py --work-dir ./path_validation_census
python check_full_history_ancestry.py --work-dir ./path_validation_census
python check_move_destinations.py --work-dir ./path_validation_census
python finalize_path_validation.py --work-dir ./path_validation_census
python summarize_source_reasons.py \
  --final ./path_validation_census/path_validation_final.csv \
  --out source_reason_descriptive_results.csv
```

The full-history script retries cases unresolved after deepening and writes `path_validation_ancestry_full_history_results.csv`. Remote availability can change; the committed outputs preserve the observed checks.

## Limitations

Git-tree checks compare path presence, not file contents, semantic equivalence, or developer intent. Source cause labels are not validated and describe the initiating event. The strict path-presence return statistic is conditioned on candidate construction and must not be called a reversal-validity rate. Independent semantic coding of removal intent remains future work.
