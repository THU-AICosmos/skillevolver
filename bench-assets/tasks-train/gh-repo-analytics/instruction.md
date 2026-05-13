I'm putting together a brief "November sprint retrospective" report for the `npm/cli` repository, and I need your help turning raw GitHub activity data into a concise, meeting-ready summary.

For the period 2024-11-01 to 2024-11-30, please gather the following information:

# Pull Requests

- Count the total number of PRs created during November.
- Report how many of those PRs have been merged and how many are still open (as of today).
- Calculate the average time-to-merge (in days) across all merged PRs, measured from PR creation time to merge time, rounded to one decimal place.
- Identify the contributor who opened the most PRs during the month.

# Issues

- Count the total number of issues created during November.
- Count how many of those issues are bug reports. A bug report is any issue where at least one label contains the substring `bug` (e.g., `Bug`, `kind/bug`, `type: bug`, etc.).
- Count how many bug report issues are still open.

Please compile everything into a `summary.json` file and place it in the `/app/` directory. The JSON must use this exact structure:

```json
{
  "pulls": {
    "count": <int>,
    "merged_count": <int>,
    "open_count": <int>,
    "mean_merge_days": <float>,
    "most_active_author": <str>
  },
  "issues": {
    "count": <int>,
    "bugs": <int>,
    "open_bugs": <int>
  }
}
```
