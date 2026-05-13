#!/bin/bash
# Oracle solution for the TRAIN variant of dapt-intrusion-detection.
#
# Streams /root/packets.pcap with scapy's PcapReader (memory-bounded) to avoid
# pulling the full capture into RAM.  The validation variant uses a ~32 MB DAPT
# capture; a streaming parse generalises to that scale, an rdpcap() load does
# not.  All per-packet state is accumulated in counters / defaultdicts in a
# single pass, then summary metrics are computed at the end.
#
# Dominant-protocol tiebreak priority (when packet counts are equal): tcp > udp
# > icmp > arp.  The check never fires on this variant (TCP is plurality) but we
# document the rule here for the distilled skill to capture.

set -e

echo "=== Network Analysis (train variant, streaming) ==="

python3 << 'PYTHON_SCRIPT'
import csv
import math
from collections import Counter, defaultdict

from scapy.all import ARP, ICMP, IP, TCP, UDP, Ether, PcapReader

PCAP_FILE = "/root/packets.pcap"
CSV_FILE = "/root/network_analysis.csv"


def shannon_entropy(counter):
    total = sum(counter.values())
    if total == 0:
        return 0.0
    h = 0.0
    for c in counter.values():
        if c > 0:
            p = c / total
            h -= p * math.log2(p)
    return h


def write_csv(results, csv_path):
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value"])
        writer.writeheader()
        for row in rows:
            metric = (row.get("metric") or "").strip()
            if metric.startswith("#") or metric not in results:
                writer.writerow(row)
            else:
                writer.writerow({"metric": metric, "value": results[metric]})


# ---------------------------------------------------------------------------
# Streaming pass — single iteration over the pcap.
# ---------------------------------------------------------------------------
print(f"Streaming PCAP: {PCAP_FILE}")

# Overall counters
frame_count = 0
tcp_count = udp_count = icmp_count = arp_count = ip_count = 0
total_octets = 0
min_size = None
max_size = 0

# Timestamps collected only as a flat list of floats (cheap vs. full packets)
timestamps = []

# Endpoint diversity
dst_ports = Counter()
src_ports = Counter()
src_ips = Counter()
dst_ips = Counter()

# Conversation graph
edges = set()
indeg = defaultdict(set)
outdeg = defaultdict(set)

# Byte roles
sent = defaultdict(int)
recv = defaultdict(int)

# Flows (5-tuple) and per-flow timestamps for per-flow beaconing detection
flows = set()
flow_ts = defaultdict(list)  # flow_key -> sorted list of packet timestamps

# Port-scan signals
per_src_ports = defaultdict(Counter)
per_src_total_tcp = defaultdict(int)
per_src_syn_only = defaultdict(int)


with PcapReader(PCAP_FILE) as reader:
    for pkt in reader:
        frame_count += 1
        size = len(pkt)
        total_octets += size
        min_size = size if min_size is None or size < min_size else min_size
        max_size = size if size > max_size else max_size
        if hasattr(pkt, "time"):
            timestamps.append(float(pkt.time))

        has_ip = IP in pkt
        has_tcp = TCP in pkt
        has_udp = UDP in pkt
        has_icmp = ICMP in pkt
        has_arp = ARP in pkt

        if has_ip:
            ip_count += 1
            s = pkt[IP].src
            d = pkt[IP].dst
            src_ips[s] += 1
            dst_ips[d] += 1
            edges.add((s, d))
            outdeg[s].add(d)
            indeg[d].add(s)
            sent[s] += size
            recv[d] += size

        if has_tcp:
            tcp_count += 1
            sp = int(pkt[TCP].sport)
            dp = int(pkt[TCP].dport)
            dst_ports[dp] += 1
            src_ports[sp] += 1
            if has_ip:
                flow = (pkt[IP].src, pkt[IP].dst, sp, dp, "TCP")
                flows.add(flow)
                if timestamps:
                    flow_ts[flow].append(timestamps[-1])
                # Port-scan per-source
                src_ip = pkt[IP].src
                per_src_ports[src_ip][dp] += 1
                per_src_total_tcp[src_ip] += 1
                flags = int(pkt[TCP].flags)
                if (flags & 0x02) and not (flags & 0x10):  # SYN set, ACK unset
                    per_src_syn_only[src_ip] += 1
        elif has_udp:
            udp_count += 1
            sp = int(pkt[UDP].sport)
            dp = int(pkt[UDP].dport)
            dst_ports[dp] += 1
            src_ports[sp] += 1
            if has_ip:
                flow = (pkt[IP].src, pkt[IP].dst, sp, dp, "UDP")
                flows.add(flow)
                if timestamps:
                    flow_ts[flow].append(timestamps[-1])
        elif has_icmp:
            icmp_count += 1
        if has_arp:
            arp_count += 1

print(f"Streamed {frame_count} packets")

# ---------------------------------------------------------------------------
# Summary computation
# ---------------------------------------------------------------------------
results = {}

# Volume and protocol mix
results["frame_count"] = frame_count
results["tcp_packet_count"] = tcp_count
results["udp_packet_count"] = udp_count
results["icmp_packet_count"] = icmp_count
results["protocol_arp"] = arp_count
results["protocol_ip_total"] = ip_count

# Dominant protocol (ties broken: tcp > udp > icmp > arp)
proto_counts = [
    ("tcp", tcp_count),
    ("udp", udp_count),
    ("icmp", icmp_count),
    ("arp", arp_count),
]
# max(...) with a stable key — Python's max returns the first item on ties,
# and the list is already in priority order, so plain max() works.
results["dominant_protocol"] = max(proto_counts, key=lambda x: x[1])[0]

# Byte counters
results["total_octets"] = total_octets
results["mean_frame_length"] = round(total_octets / frame_count, 2) if frame_count else 0.0
results["smallest_frame"] = min_size if min_size is not None else 0
results["largest_frame"] = max_size

# Capture rate
timestamps.sort()
if len(timestamps) > 1:
    start = timestamps[0]
    end = timestamps[-1]
    results["capture_span_seconds"] = round(end - start, 2)
    buckets = defaultdict(int)
    for ts in timestamps:
        buckets[int((ts - start) // 60)] += 1
    counts = list(buckets.values())
    results["peak_minute_rate"] = max(counts)
    results["mean_minute_rate"] = round(sum(counts) / len(counts), 2)
    results["floor_minute_rate"] = min(counts)
else:
    results["capture_span_seconds"] = 0.0
    results["peak_minute_rate"] = frame_count
    results["mean_minute_rate"] = float(frame_count)
    results["floor_minute_rate"] = frame_count

# Endpoint diversity
results["dest_port_entropy"] = round(shannon_entropy(dst_ports), 4)
results["source_port_entropy"] = round(shannon_entropy(src_ports), 4)
results["unique_dest_ports"] = len(dst_ports)
results["unique_source_ports"] = len(src_ports)
results["source_ip_entropy"] = round(shannon_entropy(src_ips), 4)
results["dest_ip_entropy"] = round(shannon_entropy(dst_ips), 4)

# Conversation graph
all_nodes = set(indeg) | set(outdeg)
n = len(all_nodes)
results["host_count"] = n
results["conversation_edges"] = len(edges)
possible = n * (n - 1) if n > 1 else 1
results["graph_density"] = round(len(edges) / possible, 6)
results["max_fanin"] = max((len(v) for v in indeg.values()), default=0)
results["max_fanout"] = max((len(v) for v in outdeg.values()), default=0)

# Inter-arrival stats
if len(timestamps) > 1:
    iats = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
    iat_mean = sum(iats) / len(iats)
    iat_var = sum((x - iat_mean) ** 2 for x in iats) / len(iats)
    iat_std = math.sqrt(iat_var)
    results["interarrival_mean"] = round(iat_mean, 6)
    results["interarrival_variance"] = round(iat_var, 6)
    results["interarrival_cv"] = round(iat_std / iat_mean, 4) if iat_mean > 0 else 0.0
else:
    results["interarrival_mean"] = 0.0
    results["interarrival_variance"] = 0.0
    results["interarrival_cv"] = 0.0

# Producer / consumer counts
producers = consumers = 0
for ip in all_nodes:
    s_bytes, r_bytes = sent.get(ip, 0), recv.get(ip, 0)
    tot = s_bytes + r_bytes
    if tot > 0:
        pcr = (s_bytes - r_bytes) / tot
        if pcr > 0.2:
            producers += 1
        elif pcr < -0.2:
            consumers += 1
results["producer_hosts"] = producers
results["consumer_hosts"] = consumers

# Flow enumeration
results["distinct_flows"] = len(flows)
results["tcp_flow_count"] = sum(1 for f in flows if f[4] == "TCP")
results["udp_flow_count"] = sum(1 for f in flows if f[4] == "UDP")
bidir = 0
for s_ip, d_ip, sp, dp, pr in flows:
    if (d_ip, s_ip, dp, sp, pr) in flows:
        bidir += 1
results["paired_flows"] = bidir // 2

# Threat indicators
# Port scan: per-source entropy > 6.0 AND SYN-only ratio > 0.7 AND >100 unique
# destination ports AND at least 50 TCP packets.
has_port_scan = False
for s_ip, port_ctr in per_src_ports.items():
    total = per_src_total_tcp[s_ip]
    if total < 50:
        continue
    h = shannon_entropy(port_ctr)
    ratio = per_src_syn_only[s_ip] / total
    if h > 6.0 and ratio > 0.7 and len(port_ctr) > 100:
        has_port_scan = True
        break
results["port_scan_flag"] = "true" if has_port_scan else "false"

# DoS spike: peak minute bucket / mean minute bucket > 20.
if results["mean_minute_rate"]:
    dos_ratio = results["peak_minute_rate"] / results["mean_minute_rate"]
    results["dos_spike_flag"] = "true" if dos_ratio > 20 else "false"
else:
    results["dos_spike_flag"] = "false"

# Beaconing: any single 5-tuple flow has >=5 packets AND that flow's IAT CV < 0.5.
has_beacon = False
for flow, ts_list in flow_ts.items():
    if len(ts_list) < 5:
        continue
    ts_sorted = sorted(ts_list)
    iats = [ts_sorted[i + 1] - ts_sorted[i] for i in range(len(ts_sorted) - 1)]
    m = sum(iats) / len(iats)
    if m <= 0:
        continue
    v = sum((x - m) ** 2 for x in iats) / len(iats)
    cv = math.sqrt(v) / m
    if cv < 0.5:
        has_beacon = True
        break
results["beaconing_flag"] = "true" if has_beacon else "false"

# Benign = not port_scan and not dos_spike and not beaconing
any_red_flag = any(
    results[k] == "true"
    for k in ("port_scan_flag", "dos_spike_flag", "beaconing_flag")
)
results["benign_traffic_flag"] = "false" if any_red_flag else "true"

print(f"\nWriting results to {CSV_FILE}")
write_csv(results, CSV_FILE)

print("\nResults:")
for k, v in sorted(results.items()):
    print(f"  {k}: {v}")
print("\nDone!")
PYTHON_SCRIPT
