#!/bin/bash
set -e

cat > /tmp/verify_bibliography.py << 'PYEOF'
#!/usr/bin/env python3
"""
Bibliography Verification Tool

Checks academic references in a BibTeX file against online databases
to identify fabricated or hallucinated entries.

Verification pipeline:
  Step 1 - DOI lookup via CrossRef API
  Step 2 - Title-based search on CrossRef
  Step 3 - Fallback lookup on Semantic Scholar

A reference is flagged as fabricated when:
  - Its DOI returns a 404 from CrossRef
  - No title match is found in either CrossRef or Semantic Scholar
"""

import re
import sys
import json
import time
import requests
from urllib.parse import quote
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


@dataclass
class VerificationOutcome:
    """Holds the verification outcome for one bibliography entry."""
    bib_key: str
    bib_type: str
    flagged: bool
    score: float
    notes: List[str] = field(default_factory=list)
    status: str = "pending"
    entry_fields: Dict = field(default_factory=dict)
    match_info: Optional[Dict] = None


def strip_bibtex_markup(raw: str) -> str:
    """Remove BibTeX curly braces and backslashes."""
    cleaned = re.sub(r'[{}\\]', '', raw)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def read_bib_entries(path: str) -> List[Dict]:
    """Parse a .bib file into a list of entry dicts."""
    with open(path, 'r', encoding='utf-8') as fh:
        raw = fh.read()

    entries = []
    entry_re = r'@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)\n\}'
    for m in re.finditer(entry_re, raw, re.DOTALL | re.IGNORECASE):
        etype = m.group(1).lower()
        ekey = m.group(2).strip()
        body = m.group(3)

        fields = {}
        fld_re = r'(\w+)\s*=\s*\{([^}]*)\}|(\w+)\s*=\s*"([^"]*)"'
        for fm in re.finditer(fld_re, body):
            if fm.group(1):
                fname, fval = fm.group(1).lower(), fm.group(2)
            else:
                fname, fval = fm.group(3).lower(), fm.group(4)
            fields[fname] = strip_bibtex_markup(fval)

        entries.append({'type': etype, 'key': ekey, 'fields': fields})

    return entries


def compute_jaccard(a: str, b: str) -> float:
    """Word-level Jaccard similarity between two strings."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def normalize_for_matching(t: str) -> str:
    """Lowercase and strip punctuation for title matching."""
    t = t.lower()
    t = re.sub(r'[^\w\s]', '', t)
    return ' '.join(t.split())


class BibliographyVerifier:
    """Verifies bibliography entries against academic databases."""

    def __init__(self):
        self.http = requests.Session()
        self.http.headers['User-Agent'] = (
            'BibliographyVerifier/1.0 '
            '(Academic Reference Validation; mailto:verify@example.org)'
        )

    def _log(self, msg: str):
        print(msg, file=sys.stderr)

    # ---- CrossRef DOI check ----
    def check_doi(self, doi_str: str) -> Tuple[bool, Optional[Dict]]:
        if not doi_str:
            return False, None
        doi_str = doi_str.strip()
        for pfx in ['https://doi.org/', 'http://doi.org/', 'doi:']:
            if doi_str.startswith(pfx):
                doi_str = doi_str[len(pfx):]
        try:
            resp = self.http.get(
                f'https://api.crossref.org/works/{doi_str}', timeout=15
            )
            if resp.status_code == 200:
                msg = resp.json().get('message', {})
                cr_title = (msg.get('title') or [''])[0]
                dp = msg.get('published-print', {}).get('date-parts', [[]])
                if not dp or not dp[0]:
                    dp = msg.get('published-online', {}).get('date-parts', [[]])
                yr = str(dp[0][0]) if dp and dp[0] else None
                return True, {'title': cr_title, 'year': yr, 'doi': doi_str}
            return False, None
        except Exception as exc:
            self._log(f'  DOI check error: {exc}')
            return False, None

    # ---- CrossRef title search ----
    def search_by_title(self, title: str, author: str = '') -> Tuple[bool, Optional[Dict]]:
        if not title:
            return False, None
        try:
            q = f'query.title={quote(title[:200])}'
            if author:
                first_a = author.split(' and ')[0]
                lname = first_a.split(',')[0].strip() if ',' in first_a else first_a.split()[-1]
                if lname:
                    q += f'&query.author={quote(lname)}'
            resp = self.http.get(
                f'https://api.crossref.org/works?{q}&rows=5', timeout=15
            )
            if resp.status_code == 200:
                items = resp.json().get('message', {}).get('items', [])
                for item in items:
                    it = (item.get('title') or [''])[0]
                    sim = compute_jaccard(
                        normalize_for_matching(title),
                        normalize_for_matching(it),
                    )
                    if sim >= 0.7:
                        return True, {'title': it, 'doi': item.get('DOI', ''), 'sim': sim}
            return False, None
        except Exception as exc:
            self._log(f'  CrossRef search error: {exc}')
            return False, None

    # ---- Semantic Scholar fallback ----
    def search_semantic_scholar(self, title: str, retries: int = 5) -> Tuple[bool, Optional[Dict]]:
        if not title:
            return False, None
        url = (
            f'https://api.semanticscholar.org/graph/v1/paper/search'
            f'?query={quote(title[:200])}&limit=5'
            f'&fields=title,authors,year,venue'
        )
        for attempt in range(retries):
            try:
                resp = self.http.get(url, timeout=15)
                if resp.status_code == 200:
                    papers = resp.json().get('data', [])
                    for p in papers:
                        pt = p.get('title', '')
                        sim = compute_jaccard(
                            normalize_for_matching(title),
                            normalize_for_matching(pt),
                        )
                        if sim >= 0.7:
                            return True, {'title': pt, 'venue': p.get('venue', ''), 'sim': sim}
                    return False, None
                elif resp.status_code == 429:
                    wait = 2 ** attempt * 3
                    self._log(f'  S2 rate-limited; sleeping {wait}s (try {attempt+1}/{retries})')
                    time.sleep(wait)
                    continue
                else:
                    return False, None
            except Exception as exc:
                self._log(f'  S2 search error: {exc}')
                return False, None
        return False, None

    # ---- Main verification loop ----
    def verify_all(self, bib_path: str) -> List[VerificationOutcome]:
        entries = read_bib_entries(bib_path)
        self._log(f'Loaded {len(entries)} entries from {bib_path}\n')
        outcomes = []

        for idx, ent in enumerate(entries):
            flds = ent['fields']
            doi_val = flds.get('doi', '')
            title_val = flds.get('title', '')
            author_val = flds.get('author', '')
            self._log(f'[{idx+1}/{len(entries)}] {ent["key"]}')

            outcome = VerificationOutcome(
                bib_key=ent['key'], bib_type=ent['type'],
                flagged=False, score=0.0,
                entry_fields=flds,
            )

            if doi_val:
                self._log(f'  Checking DOI: {doi_val}')
                ok, meta = self.check_doi(doi_val)
                if ok:
                    outcome.status = 'confirmed'
                    outcome.match_info = meta
                    self._log('  -> Confirmed via DOI')
                else:
                    outcome.flagged = True
                    outcome.score = 0.95
                    outcome.status = 'fabricated'
                    outcome.notes.append(f'DOI not found in CrossRef: {doi_val}')
                    self._log('  -> FABRICATED (invalid DOI)')
                time.sleep(1.0)
            elif title_val:
                self._log('  Searching CrossRef by title...')
                ok, meta = self.search_by_title(title_val, author_val)
                if ok:
                    outcome.status = 'confirmed'
                    outcome.match_info = meta
                    self._log(f'  -> Confirmed in CrossRef (sim={meta.get("sim",0):.2f})')
                else:
                    time.sleep(1.5)
                    self._log('  Searching Semantic Scholar...')
                    ok, meta = self.search_semantic_scholar(title_val)
                    if ok:
                        outcome.status = 'confirmed'
                        outcome.match_info = meta
                        self._log(f'  -> Confirmed in S2 (sim={meta.get("sim",0):.2f})')
                    else:
                        outcome.flagged = True
                        outcome.score = 0.85
                        outcome.status = 'fabricated'
                        outcome.notes.append('Not found in CrossRef or Semantic Scholar')
                        self._log('  -> FABRICATED (not in any database)')
                time.sleep(1.0)
            else:
                outcome.flagged = True
                outcome.score = 0.5
                outcome.status = 'fabricated'
                outcome.notes.append('No DOI or title available')

            outcomes.append(outcome)

        return outcomes


# ---- Execute ----
verifier = BibliographyVerifier()
all_outcomes = verifier.verify_all('/root/references.bib')

fabricated = [o for o in all_outcomes if o.flagged]
confirmed = [o for o in all_outcomes if o.status == 'confirmed']

# Collect and sort titles
flagged_titles = sorted(
    o.entry_fields.get('title', '') for o in fabricated if o.entry_fields.get('title')
)

print(f'\n{"=" * 55}', file=sys.stderr)
print('VERIFICATION SUMMARY', file=sys.stderr)
print(f'{"=" * 55}', file=sys.stderr)
print(f'Total entries: {len(all_outcomes)}', file=sys.stderr)
print(f'Confirmed real: {len(confirmed)}', file=sys.stderr)
print(f'Flagged fabricated: {len(fabricated)}', file=sys.stderr)
if flagged_titles:
    print('\nFabricated entries:', file=sys.stderr)
    for t in flagged_titles:
        print(f'  * {t}', file=sys.stderr)

# Write output
with open('/root/verification_report.json', 'w') as out:
    json.dump({'suspicious_entries': flagged_titles}, out, indent=2)
print('\nReport saved to /root/verification_report.json', file=sys.stderr)
PYEOF

python3 /tmp/verify_bibliography.py
echo "Verification complete."
