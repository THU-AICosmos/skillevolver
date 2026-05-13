#!/bin/bash
set -e

python3 << 'PYEOF'
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path


TARGET_REPO = "npm/cli"
PERIOD = "2024-11-01..2024-11-30"
DEST = Path("/app/summary.json")


def run_gh(arguments: str) -> list:
    proc = subprocess.run(
        f"gh {arguments}".split(),
        capture_output=True, text=True
    )
    raw = proc.stdout.strip()
    return json.loads(raw) if raw else []


def compute_duration_days(start_iso: str, end_iso: str) -> float:
    fmt = lambda s: datetime.fromisoformat(s.replace('Z', '+00:00'))
    return (fmt(end_iso) - fmt(start_iso)).total_seconds() / 86400


def label_contains_bug(item: dict) -> bool:
    for lbl in item.get('labels', []):
        if 'bug' in lbl['name'].lower():
            return True
    return False


def gather_pull_request_stats():
    records = run_gh(
        f"pr list -R {TARGET_REPO} --state all "
        f"--search created:{PERIOD} "
        f"--json number,state,author,createdAt,mergedAt"
    )

    merged_records = [r for r in records if r['state'] == 'MERGED' and r.get('mergedAt')]
    open_records = [r for r in records if r['state'] == 'OPEN']

    author_counts = Counter(
        r['author']['login'] for r in records if r.get('author')
    )
    leading_author = author_counts.most_common(1)[0][0] if author_counts else ""

    if merged_records:
        total_days = sum(
            compute_duration_days(r['createdAt'], r['mergedAt'])
            for r in merged_records
        )
        avg_days = round(total_days / len(merged_records), 1)
    else:
        avg_days = 0.0

    return {
        "count": len(records),
        "merged_count": len(merged_records),
        "open_count": len(open_records),
        "mean_merge_days": avg_days,
        "most_active_author": leading_author,
    }


def gather_issue_stats():
    records = run_gh(
        f"issue list -R {TARGET_REPO} --state all "
        f"--search created:{PERIOD} "
        f"--json number,state,labels"
    )

    bug_items = [r for r in records if label_contains_bug(r)]
    open_bug_items = [r for r in bug_items if r['state'] == 'OPEN']

    return {
        "count": len(records),
        "bugs": len(bug_items),
        "open_bugs": len(open_bug_items),
    }


if __name__ == '__main__':
    report = {
        "pulls": gather_pull_request_stats(),
        "issues": gather_issue_stats(),
    }
    DEST.write_text(json.dumps(report, indent=2))
    print(f"Written to {DEST}")
    print(json.dumps(report, indent=2))
PYEOF
