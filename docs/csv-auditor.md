# CSV Auditor

Check an export before putting its numbers into a report. Select a key, numerical column and date column; the agent can inspect headers, run checks and explain the affected rows.

```bash
python3 -m agentkit csv-auditor --demo
python3 -m agentkit csv-auditor --workspace examples --model YOUR_INSTALLED_MODEL \
  --task "Audit observations.csv using id, volume and date, as of 2026-09-29. A record is stale after 7 days. Explain the problems with row references."
```

Checks: missing values, repeated nonblank keys, invalid/nonfinite numbers, stale and future dates, and extreme numerical observations. Outlier rule: absolute distance from the median greater than 6 median absolute deviations. If MAD is zero, it explicitly declines outlier classification. This threshold is a screening heuristic, not a statistical finding or fraud verdict.

Rows reference the CSV header as row 1 for ordinary one-line records. Multiline quoted cells can make these logical record indices differ from physical file line numbers. Numeric sums are raw-row totals and include duplicates; deduplicate under an explicit policy before using them in analysis. No rows are changed automatically.

Tools: `list_files`, `read_excerpt`, `audit_csv`.
