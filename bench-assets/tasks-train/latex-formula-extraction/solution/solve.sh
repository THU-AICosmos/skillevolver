#!/bin/bash
set -euo pipefail

# Real pipeline for latex-formula-extraction (training variant).
#
# Stages:
#   1. Convert the PDF to Markdown with marker_single (the CLI shipped by
#      marker-pdf). This emits display-math as three consecutive lines:
#          $$
#          <formula body, possibly with \tag{...} / \quad (n) / trailing ,.>
#          $$
#   2. Parse those triples out of the Markdown, normalising whitespace and
#      stripping numbering / trailing punctuation that marker carries over
#      from the surrounding sentence.
#   3. Detect bracket-asymmetry typos of the form \left\{ ... \right] (or
#      \left( ... \right] / \left[ ... \right) etc.) and emit a corrected
#      duplicate whose right delimiter matches the left one.
#   4. Write one formula per line, wrapped in $$...$$, to the expected path.

PDF=/root/stat_learning_paper.pdf
OUT=/root/extracted_stat_formulas.md
TMP=$(mktemp -d -t marker_stat_XXXXXX)
trap 'rm -rf "$TMP"' EXIT

echo "[stage 1/3] marker_single -> Markdown"
marker_single "$PDF" \
    --output_format markdown \
    --disable_image_extraction \
    --output_dir "$TMP"

# marker_single writes $TMP/<pdf_stem>/<pdf_stem>.md
MD_PATH=$(find "$TMP" -maxdepth 3 -type f -name '*.md' | head -n 1)
if [ -z "${MD_PATH:-}" ]; then
    echo "ERROR: marker_single produced no .md in $TMP" >&2
    exit 1
fi

echo "[stage 2/3] parse display-math triples from $MD_PATH"
echo "[stage 3/3] balance-check brackets and emit corrected duplicate(s)"

python3 - "$MD_PATH" "$OUT" <<'PY'
import re
import sys
from pathlib import Path

md_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])

# Delimiter pairs that are considered "matched" when a \left X is closed by a
# \right Y. Anything in LEFTS paired with anything in RIGHTS that is NOT its
# natural partner is treated as a typo and fixed by replacing the right-side
# delimiter with the partner of the left one.
LEFT_TO_RIGHT = {
    "(": ")",
    "[": "]",
    "\\{": "\\}",
    "\\langle": "\\rangle",
    "\\lfloor": "\\rfloor",
    "\\lceil": "\\rceil",
    "|": "|",
    "\\|": "\\|",
    ".": ".",
}


def sanitize(body: str) -> str:
    """Strip numbering noise and trailing punctuation, collapse whitespace."""
    s = re.sub(r"\\tag\{[^}]*\}", "", body)
    s = re.sub(r"\\(?:quad|qquad)\s*\(?\d+\)?", "", s)
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[.,]\s*$", "", s)
    return s


def parse_triples(md_text: str) -> list[str]:
    """
    marker_single emits display math as:
        $$
        <body>
        $$
    Collapse each such triple into a single cleaned formula string (no $$).
    """
    lines = md_text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "$$" and i + 2 < len(lines) and lines[i + 2].strip() == "$$":
            cleaned = sanitize(lines[i + 1])
            if cleaned:
                out.append(cleaned)
            i += 3
            continue
        # Also accept single-line $$...$$ just in case.
        stripped = lines[i].strip()
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
            cleaned = sanitize(stripped[2:-2])
            if cleaned:
                out.append(cleaned)
        i += 1
    return out


# Regex matching any \left X paired with any \right Y (non-greedy between).
LEFT_RE = re.compile(
    r"\\left(\\\{|\\\||\\langle|\\lfloor|\\lceil|\(|\[|\||\.)"
)
RIGHT_RE = re.compile(
    r"\\right(\\\}|\\\||\\rangle|\\rfloor|\\rceil|\)|\]|\||\.)"
)


def find_bracket_typo_fix(formula: str) -> str | None:
    """
    Walk \left/\right pairs in order. If any pair is mismatched according to
    LEFT_TO_RIGHT, return a fixed copy of the formula with the first such
    \right <delim> replaced so it matches its opening \left. Otherwise return
    None.
    """
    tokens = []  # list of ("L"|"R", delim, start, end)
    for m in LEFT_RE.finditer(formula):
        tokens.append(("L", m.group(1), m.start(), m.end()))
    for m in RIGHT_RE.finditer(formula):
        tokens.append(("R", m.group(1), m.start(), m.end()))
    tokens.sort(key=lambda t: t[2])

    stack = []
    for kind, delim, s, e in tokens:
        if kind == "L":
            stack.append((delim, s, e))
        else:
            if not stack:
                continue  # unmatched \right, leave alone
            left_delim, _, _ = stack.pop()
            expected_right = LEFT_TO_RIGHT.get(left_delim)
            if expected_right is None:
                continue
            if delim != expected_right:
                fixed = formula[:s] + "\\right" + expected_right + formula[e:]
                return fixed
    return None


md_text = md_path.read_text(encoding="utf-8")
formulas = parse_triples(md_text)

final: list[str] = []
# 1) All original formulas first (deduped, preserving order).
seen = set()
for f in formulas:
    if f not in seen:
        final.append(f)
        seen.add(f)

# 2) Append a fixed duplicate for each formula that has a bracket typo.
fixes = []
for f in formulas:
    fixed = find_bracket_typo_fix(f)
    if fixed and fixed not in seen:
        fixes.append(fixed)
        seen.add(fixed)
final.extend(fixes)

out_lines = [f"$${f}$$" for f in final]
out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
print(f"Wrote {len(out_lines)} formulas ({len(formulas)} original + {len(fixes)} fixed) to {out_path}")
PY

echo "Done: $(wc -l < "$OUT") lines written to $OUT"
