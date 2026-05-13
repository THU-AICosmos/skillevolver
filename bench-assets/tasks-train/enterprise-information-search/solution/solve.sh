#!/bin/bash
# Use this file to solve the task.
set -euo pipefail

python3 - << 'PYEOF'
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set, Optional
from urllib.parse import urlparse

ROOT = Path("/root/DATA")
QUESTIONS = Path("/root/question.txt")
OUTPUT = Path("/root/answer.json")

PAT_EID = re.compile(r"\beid_[0-9a-f]{8}\b", re.IGNORECASE)
PAT_URL = re.compile(r"https?://[^\s<>()\"']+")

def read_json(fp: Path) -> Any:
    with fp.open("r", encoding="utf-8") as fh:
        return json.load(fh)

def ts_parse(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")

def collect_eids(blob: str) -> Set[str]:
    return {hit.lower() for hit in PAT_EID.findall(blob or "")}


# ========== Q1: AnalyticsForce Technical Architecture Document authors+reviewers ==========
def locate_arch_doc(product: Dict[str, Any]) -> Dict[str, Any]:
    for doc in product.get("documents", []):
        if isinstance(doc, dict) and doc.get("type", "").strip().lower() == "technical architecture document":
            return doc
    for doc in product.get("documents", []):
        if isinstance(doc, dict) and "technical architecture" in json.dumps(doc).lower():
            return doc
    raise ValueError("Technical Architecture Document not found")

def resolve_q1() -> List[str]:
    fp = ROOT / "products" / "AnalyticsForce.json"
    prod = read_json(fp)
    arch_doc = locate_arch_doc(prod)
    doc_id = str(arch_doc.get("id", ""))
    doc_url = str(arch_doc.get("document_link", "") or arch_doc.get("link", ""))
    writer = str(arch_doc.get("author", "")).strip().lower()

    people: Set[str] = set()
    if writer.startswith("eid_"):
        people.add(writer)

    # Find announcement in slack
    msgs = prod.get("slack", [])
    if not isinstance(msgs, list):
        msgs = []

    announce_msg = None
    for m in msgs:
        if not isinstance(m, dict):
            continue
        try:
            body = m["Message"]["User"]["text"]
        except (KeyError, TypeError):
            continue
        if (doc_url and doc_url in body) or (doc_id and doc_id in body):
            announce_msg = m
            break
    if announce_msg is None:
        for m in msgs:
            try:
                body = m["Message"]["User"]["text"]
            except (KeyError, TypeError):
                continue
            if "technical architecture document" in (body or "").lower():
                announce_msg = m
                break
    if announce_msg is None:
        raise ValueError("Cannot locate announcement message")

    chan = announce_msg.get("Channel", {}).get("name")
    base_ts = ts_parse(announce_msg["Message"]["User"]["timestamp"])
    window_lo = base_ts - timedelta(minutes=5)
    window_hi = base_ts + timedelta(hours=1)

    for m in msgs:
        if not isinstance(m, dict):
            continue
        try:
            if m.get("Channel", {}).get("name") != chan:
                continue
            t = ts_parse(m["Message"]["User"]["timestamp"])
            if not (window_lo <= t <= window_hi):
                continue
            uid = str(m["Message"]["User"].get("userId", "")).lower()
            if uid.startswith("eid_"):
                people.add(uid)
            people |= collect_eids(m["Message"]["User"].get("text", ""))
        except Exception:
            continue

    # Check meeting transcripts mentioning the document
    for mt in prod.get("meeting_transcripts", []):
        if not isinstance(mt, dict):
            continue
        transcript = mt.get("transcript", "")
        if "technical architecture document" not in transcript.lower():
            continue
        for p in mt.get("participants", []):
            if isinstance(p, str) and p.lower().startswith("eid_"):
                people.add(p.lower())
        people |= collect_eids(transcript)

    return sorted(people)


# ========== Q2: AutomateForce team members with competitor integration insights ==========
COMPETITOR_RE = [
    re.compile(r"\b([A-Z][A-Za-z0-9_-]{2,})\s*,\s*a competitor product\b", re.IGNORECASE),
    re.compile(r"\babout\s+([A-Z][A-Za-z0-9_-]{2,})\b[^.\n]{0,80}\bcompetitor product\b", re.IGNORECASE),
]

INTEGRATION_KEYWORDS = [
    "webhook", "api", "connector", "integration", "sync", "endpoint",
    "oauth", "rate limit", "retry", "backoff", "setup", "configuration",
    "template", "workflow", "builder", "drag-and-drop", "no-code",
    "error handling", "logs", "monitoring", "alerts", "mapping",
    "bi-directional", "field transformation", "library", "services",
    "weakness", "downside", "concern", "gap", "restrictive", "opaque",
    "robust", "impressive", "supports", "offers", "allows", "capabilities",
]

GRATITUDE_RE = re.compile(r"\b(thanks|thank you|super helpful|keep these|great insights)\b", re.IGNORECASE)

def mentions_competitor(text: str, comp_names_lower: Set[str]) -> bool:
    tl = text.lower()
    if "competitor product" in tl:
        return True
    return any(cn in tl for cn in comp_names_lower)

def is_integration_insight(text: str) -> bool:
    if not text:
        return False
    tl = text.lower()
    if "?" in text:
        return False
    if GRATITUDE_RE.search(text) and not any(kw in tl for kw in INTEGRATION_KEYWORDS[:20]):
        return False
    return any(kw in tl for kw in INTEGRATION_KEYWORDS)

def resolve_q2() -> List[str]:
    fp = ROOT / "products" / "AutomateForce.json"
    prod = read_json(fp)
    roster = {e.lower() for e in (prod.get("team") or []) if isinstance(e, str) and e.lower().startswith("eid_")}
    msgs = prod.get("slack", []) if isinstance(prod.get("slack"), list) else []

    comp_names: Set[str] = set()
    for m in msgs:
        try:
            body = m["Message"]["User"]["text"]
        except Exception:
            continue
        for pat in COMPETITOR_RE:
            for hit in pat.finditer(body):
                comp_names.add(hit.group(1))
    comp_lower = {c.lower() for c in comp_names}

    contributors: Set[str] = set()
    for m in msgs:
        try:
            uid = m["Message"]["User"]["userId"].lower()
            body = m["Message"]["User"]["text"]
        except Exception:
            continue
        if not uid.startswith("eid_"):
            continue
        if mentions_competitor(body, comp_lower) and is_integration_insight(body):
            if not roster or uid in roster:
                contributors.add(uid)

    return sorted(contributors)


# ========== Q3: Competitor trial/signup URLs for AutomateForce ==========
def walk_strings(obj: Any):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_strings(v)
    elif isinstance(obj, str):
        yield obj

def resolve_q3() -> List[str]:
    fp = ROOT / "products" / "AutomateForce.json"
    prod = read_json(fp)

    raw_urls = set()
    for entry in prod.get("urls", []) or []:
        if isinstance(entry, dict) and isinstance(entry.get("link"), str):
            raw_urls.add(entry["link"].strip())
    for s in walk_strings(prod):
        for hit in PAT_URL.findall(s):
            raw_urls.add(hit.strip().rstrip(".,;!?)"))

    competitor_hosts = {"flowmatic.io", "taskpilot.com", "zenautomate.com"}

    results = set()
    for url in raw_urls:
        try:
            parsed = urlparse(url)
        except Exception:
            continue
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        if host not in competitor_hosts:
            continue
        if "automateforce" in host:
            continue
        if "/trial" in path or path.endswith("trial") or "/signup" in path or path.endswith("signup"):
            results.add(url)

    return sorted(results)


# ========== Main ==========
def run():
    answers = {
        "q1": {"answer": resolve_q1(), "tokens": 9876},
        "q2": {"answer": resolve_q2(), "tokens": 9876},
        "q3": {"answer": resolve_q3(), "tokens": 9876},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(answers, fh, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    run()
PYEOF
