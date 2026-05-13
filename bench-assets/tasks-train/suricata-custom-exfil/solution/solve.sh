#!/bin/bash
set -euo pipefail

# Oracle solution for C2 beacon detection task.
#
# Strategy:
# 1) Build a Suricata HTTP rule matching the stated behavioural requirements.
# 2) Write it to /root/local.rules.
# 3) Validate against the supplied training pcaps.

python3 <<'PYEOF'
from pathlib import Path

RULE_SID = 1000001
RULE_REV = 1

uri = "/api/v3/heartbeat"
hdr_key = "X-Beacon-Type"
hdr_val = "command"

clauses: list[str] = []
clauses.append('msg:"SkillsBench C2 beacon heartbeat"')
clauses.append("flow:established,to_server")

# HTTP method
clauses.append("http.method")
clauses.append('content:"PUT"')

# URI match
clauses.append("http.uri")
clauses.append(f'content:"{uri}"')

# Header match (case-insensitive)
clauses.append("http.header")
clauses.append(f'content:"{hdr_key}|3a| {hdr_val}"')
clauses.append("nocase")

# Body: data= with hex value >= 100 chars
clauses.append("http.request_body")
clauses.append('content:"data="')
clauses.append(r'pcre:"/(?:^|&)data=[0-9a-fA-F]{100,}(?:&|$)/"')

# Body: checksum= with exactly 40 hex chars
clauses.append(r'pcre:"/(?:^|&)checksum=[0-9a-fA-F]{40}(?:&|$)/"')

clauses.append(f"sid:{RULE_SID}")
clauses.append(f"rev:{RULE_REV}")

rule_line = "alert http any any -> any any (" + "; ".join(clauses) + ";)"

out = Path("/root/local.rules")
out.write_text(rule_line + "\n")
print(f"Rule written to {out}")
print(rule_line)
PYEOF

workdir="/tmp/suri_verify"
rm -rf "$workdir"
mkdir -p "$workdir/pos" "$workdir/neg"

# Positive pcap must trigger
suricata -c /root/suricata.yaml -S /root/local.rules -k none -r /root/pcaps/train_pos.pcap -l "$workdir/pos" >/dev/null 2>&1
if ! grep -q '"signature_id":1000001' "$workdir/pos/eve.json"; then
	echo "Validation failed: sid 1000001 missing on train_pos.pcap" >&2
	exit 1
fi

# Negative pcap must be silent
suricata -c /root/suricata.yaml -S /root/local.rules -k none -r /root/pcaps/train_neg.pcap -l "$workdir/neg" >/dev/null 2>&1
if grep -q '"signature_id":1000001' "$workdir/neg/eve.json"; then
	echo "Validation failed: unexpected sid 1000001 on train_neg.pcap" >&2
	exit 1
fi

echo "Validation passed."
