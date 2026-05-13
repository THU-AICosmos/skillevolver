#!/bin/bash

# Oracle solution for fixing build errors in StatCalc-AI/statcalc
PROJECT_ROOT=/home/github/build
REPO_PATH="$PROJECT_ROOT/failed/StatCalc-AI/statcalc"

# Step 1: Analyze and document the failures
cat > "$PROJECT_ROOT/failed/failed_reasons.txt" <<'NOTES'
Build Failure Analysis for StatCalc-AI/statcalc
================================================

Three bugs identified that cause test failures:

1. statcalc/compute.py line 11:
   - NameError: references 'value' (undefined) instead of 'values' (parameter name)
   - Function: mean()
   - Impact: All tests depending on mean() fail, including variance/std_dev

2. statcalc/render.py line 14:
   - NameError: references 'header' (undefined) instead of 'headers' (parameter name)
   - Function: format_table()
   - Impact: test_render.py::TestFormatTable tests fail

3. statcalc/render.py line 26:
   - NameError: 'json' module is used but never imported
   - Function: format_summary()
   - Impact: test_render.py::TestFormatSummary tests fail

Fix Plan:
- Patch 0: Fix the typo in compute.py (value -> values)
- Patch 1: Fix both issues in render.py (add json import + header -> headers)
NOTES

cd "$REPO_PATH"

# Step 2: Fix compute.py and generate patch_0.diff
sed -i 's/return sum(values) \/ len(value)/return sum(values) \/ len(values)/' statcalc/compute.py
git diff statcalc/compute.py > patch_0.diff
git checkout statcalc/compute.py

# Step 3: Fix render.py and generate patch_1.diff
sed -i '1a import json' statcalc/render.py
sed -i 's/enumerate(header))/enumerate(headers))/' statcalc/render.py
git diff statcalc/render.py > patch_1.diff
git checkout statcalc/render.py

# Step 4: Apply the patches
for patchfile in patch_*.diff; do
    echo "Applying: $patchfile"
    git apply "$patchfile"
    echo "---"
done

echo "All patches applied successfully."
