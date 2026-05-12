#!/bin/bash
# Oracle solution for network capacity planning audit task
# Analyzes packets.pcap and fills in capacity_audit.csv

set -e

echo "=== Network Capacity Planning Audit ==="

python3 << 'PYTHON_SCRIPT'
import csv
import math
from collections import defaultdict
from scapy.all import IP, TCP, ARP, rdpcap

PCAP_FILE = "/root/packets.pcap"
CSV_FILE = "/root/capacity_audit.csv"

print(f"Loading PCAP: {PCAP_FILE}")
packets = rdpcap(PCAP_FILE)
print(f"Loaded {len(packets)} packets")

ip_packets = [p for p in packets if IP in p]
tcp_packets = [p for p in packets if TCP in p]
arp_packets = [p for p in packets if ARP in p]

results = {}

# =====================
# Bandwidth & Payload
# =====================
packet_sizes = [len(p) for p in packets]
results["total_bytes"] = sum(packet_sizes)
results["avg_packet_size"] = round(results["total_bytes"] / len(packets), 2)
results["max_packet_size"] = max(packet_sizes)

# =====================
# Protocol Breakdown
# =====================
results["protocol_tcp"] = len(tcp_packets)
results["protocol_arp"] = len(arp_packets)
results["protocol_ip_total"] = len(ip_packets)

# =====================
# Topology Overview
# =====================
edges = set()
outdegree = defaultdict(set)
indegree = defaultdict(set)

for pkt in ip_packets:
    src, dst = pkt[IP].src, pkt[IP].dst
    edges.add((src, dst))
    outdegree[src].add(dst)
    indegree[dst].add(src)

all_nodes = set(outdegree.keys()) | set(indegree.keys())
num_nodes = len(all_nodes)
num_edges = len(edges)

results["num_nodes"] = num_nodes
results["num_edges"] = num_edges
results["max_outdegree"] = max(len(v) for v in outdegree.values()) if outdegree else 0

possible_edges = num_nodes * (num_nodes - 1) if num_nodes > 1 else 1
results["network_density"] = round(num_edges / possible_edges, 6)

# =====================
# Traffic Timing
# =====================
timestamps = sorted(float(p.time) for p in packets if hasattr(p, 'time'))
if len(timestamps) > 1:
    start_time = min(timestamps)
    end_time = max(timestamps)
    duration = end_time - start_time
    results["duration_seconds"] = round(duration, 2)

    iats = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
    iat_mean = sum(iats) / len(iats)
    iat_var = sum((x - iat_mean)**2 for x in iats) / len(iats)
    iat_std = math.sqrt(iat_var)

    results["iat_mean"] = round(iat_mean, 6)
    results["iat_variance"] = round(iat_var, 6)

# =====================
# Capacity Flags
# =====================
results["is_traffic_benign"] = "true"

# Beaconing: CV < 0.5 suggests regular robotic traffic
iat_cv = iat_std / iat_mean if iat_mean > 0 else 0
results["has_beaconing"] = "true" if iat_cv < 0.5 else "false"

# Port scan detection
from collections import Counter

src_port_counts = defaultdict(Counter)
src_syn_only = defaultdict(int)
src_total_tcp = defaultdict(int)

for pkt in tcp_packets:
    if IP in pkt and TCP in pkt:
        src = pkt[IP].src
        dst_port = pkt[TCP].dport
        flags = pkt[TCP].flags
        src_port_counts[src][dst_port] += 1
        src_total_tcp[src] += 1
        if flags & 0x02 and not (flags & 0x10):
            src_syn_only[src] += 1

def calc_port_entropy(port_counter):
    total = sum(port_counter.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in port_counter.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy

has_port_scan = False
for src in src_port_counts:
    total_pkts = src_total_tcp[src]
    if total_pkts < 50:
        continue
    port_entropy = calc_port_entropy(src_port_counts[src])
    syn_only_ratio = src_syn_only[src] / total_pkts if total_pkts > 0 else 0
    unique_ports = len(src_port_counts[src])
    if port_entropy > 6.0 and syn_only_ratio > 0.7 and unique_ports > 100:
        has_port_scan = True
        break

results["has_port_scan"] = "true" if has_port_scan else "false"

# =====================
# Write to CSV
# =====================
print(f"\nWriting results to {CSV_FILE}")

rows = []
with open(CSV_FILE, newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

with open(CSV_FILE, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['metric', 'value'])
    writer.writeheader()
    for row in rows:
        metric = (row.get('metric') or '').strip()
        if metric.startswith('#'):
            writer.writerow(row)
        elif metric in results:
            writer.writerow({'metric': metric, 'value': results[metric]})
        else:
            writer.writerow(row)

print("\nResults:")
for k, v in sorted(results.items()):
    print(f"  {k}: {v}")

print("\nDone!")
PYTHON_SCRIPT
