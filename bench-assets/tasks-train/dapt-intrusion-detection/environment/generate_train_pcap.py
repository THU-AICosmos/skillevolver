#!/usr/bin/env python3
"""
Synthetic cloud-tenant PCAP generator for the dapt-intrusion-detection TRAIN variant.

Design goals:
  * ~3500 packets total (~1-2 MB on disk).
  * Protocol mix approximately 40% ARP / 30% TCP / 20% UDP / 10% ICMP,
    so the val-side `protocol_arp` + `dominant_protocol` metrics are exercised.
  * Benign baseline with multiple TCP sessions (SYN/SYN-ACK/ACK/FIN), UDP short
    flows, and ICMP echo pairs.
  * One ARP-scan burst (high-fanout, single source probing many targets).
  * One TCP SYN-scan pattern: single source hitting 120+ distinct destination ports
    with SYN-only packets (exercises the `port_scan_flag` heuristic).
  * One DoS-style spike: concentrate enough packets in a single 60-second bucket
    that `peak_minute_rate / mean_minute_rate > 20` so `dos_spike_flag` fires.
  * One beaconing flow: a single (src,dst,sport,dport,UDP) 5-tuple with >=10
    regularly-spaced packets (IAT ~2.0 s, low CV) so per-flow beacon detection
    fires.

The oracle (solve.sh) consumes this pcap with PcapReader streaming, so we avoid
giant captures — 3.5k pkts is plenty for teaching "streaming pcap parse".

Run inside the task's Docker image:
    docker run --rm -v <env-abs>:/work <img> python3 /work/generate_train_pcap.py /work/packets.pcap
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from scapy.all import ARP, DNS, DNSQR, ICMP, IP, TCP, UDP, Ether, Raw, wrpcap


SEED = 20260422
random.seed(SEED)


def make_arp(src_mac, src_ip, dst_mac, dst_ip, op, ts):
    pkt = Ether(src=src_mac, dst=dst_mac) / ARP(
        op=op, hwsrc=src_mac, psrc=src_ip, hwdst=dst_mac, pdst=dst_ip
    )
    pkt.time = ts
    return pkt


def make_tcp(src_ip, dst_ip, sport, dport, flags, ts, payload_len=0):
    eth = Ether(src=_mac(src_ip), dst=_mac(dst_ip))
    ip = IP(src=src_ip, dst=dst_ip)
    tcp = TCP(sport=sport, dport=dport, flags=flags, seq=random.randint(1, 2**31))
    pkt = eth / ip / tcp
    if payload_len:
        pkt = pkt / Raw(load=b"X" * payload_len)
    pkt.time = ts
    return pkt


def make_udp(src_ip, dst_ip, sport, dport, ts, payload_len=20):
    eth = Ether(src=_mac(src_ip), dst=_mac(dst_ip))
    ip = IP(src=src_ip, dst=dst_ip)
    udp = UDP(sport=sport, dport=dport)
    pkt = eth / ip / udp / Raw(load=b"U" * payload_len)
    pkt.time = ts
    return pkt


def make_icmp(src_ip, dst_ip, itype, seq, ts, payload_len=28):
    eth = Ether(src=_mac(src_ip), dst=_mac(dst_ip))
    ip = IP(src=src_ip, dst=dst_ip)
    icmp = ICMP(type=itype, seq=seq)
    pkt = eth / ip / icmp / Raw(load=b"I" * payload_len)
    pkt.time = ts
    return pkt


_MAC_CACHE: dict[str, str] = {}


def _mac(ip: str) -> str:
    if ip not in _MAC_CACHE:
        octets = [int(x) for x in ip.split(".")]
        _MAC_CACHE[ip] = "02:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}".format(
            octets[0] & 0xFF, octets[1] & 0xFF, octets[2] & 0xFF,
            octets[3] & 0xFF, random.randint(0, 255),
        )
    return _MAC_CACHE[ip]


BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"


def generate(out_path: Path) -> None:
    packets = []
    t0 = 1_700_000_000.0  # fixed anchor so reruns are deterministic

    # -------------------------------------------------------------------
    # Host inventory
    # -------------------------------------------------------------------
    gateway = "10.50.0.1"
    web_clients = [f"10.50.0.{i}" for i in range(10, 22)]      # 12 clients
    web_servers = ["10.50.1.10", "10.50.1.11", "10.50.1.12"]
    dns_server = "10.50.0.53"
    ntp_server = "10.50.0.123"
    monitor = "10.50.0.200"
    scanner = "10.50.0.250"

    # -------------------------------------------------------------------
    # 1) Benign baseline — spread across ~360 s pre-burst
    # -------------------------------------------------------------------
    # 1a) ARP request/reply pairs from each client to the gateway (repeated refreshes).
    t = t0
    for client in web_clients:
        for _ in range(8):  # 8 refreshes per client -> 192 arp packets
            packets.append(make_arp(_mac(client), client, BROADCAST_MAC, gateway, 1, t))
            t += 0.005
            packets.append(make_arp(_mac(gateway), gateway, _mac(client), client, 2, t))
            t += random.uniform(0.4, 1.2)
    # 1b) Gateway ARPing around for other hosts (multiple rounds).
    for _ in range(6):  # 6 rounds * 5 hosts * 2 = 60 arp
        for ip in web_servers + [dns_server, ntp_server, monitor]:
            packets.append(make_arp(_mac(gateway), gateway, BROADCAST_MAC, ip, 1, t))
            t += 0.01
            packets.append(make_arp(_mac(ip), ip, _mac(gateway), gateway, 2, t))
            t += random.uniform(0.3, 0.8)
    # 1c) Inter-client ARP (who-has within subnet) — spread across capture.
    for _ in range(4):  # 4 rounds * 12 clients * 2 = 96 arp
        for client in web_clients:
            peer = random.choice([c for c in web_clients if c != client])
            packets.append(make_arp(_mac(client), client, BROADCAST_MAC, peer, 1, t))
            t += 0.005
            packets.append(make_arp(_mac(peer), peer, _mac(client), client, 2, t))
            t += random.uniform(0.2, 0.6)

    # 1d) TCP web sessions: each client talks to a web server.
    ephemeral = 40000
    for client in web_clients:
        server = random.choice(web_servers)
        sport = ephemeral
        ephemeral += 1
        dport = random.choice([80, 443])
        # 3-way handshake
        packets.append(make_tcp(client, server, sport, dport, "S", t)); t += 0.01
        packets.append(make_tcp(server, client, dport, sport, "SA", t)); t += 0.01
        packets.append(make_tcp(client, server, sport, dport, "A", t)); t += 0.05
        # data exchange (2-4 packets each way)
        for _ in range(random.randint(2, 4)):
            packets.append(make_tcp(client, server, sport, dport, "PA", t,
                                    payload_len=random.randint(40, 400)))
            t += random.uniform(0.03, 0.15)
            packets.append(make_tcp(server, client, dport, sport, "PA", t,
                                    payload_len=random.randint(80, 900)))
            t += random.uniform(0.05, 0.25)
        # graceful close
        packets.append(make_tcp(client, server, sport, dport, "FA", t)); t += 0.01
        packets.append(make_tcp(server, client, dport, sport, "FA", t)); t += 0.02
        packets.append(make_tcp(client, server, sport, dport, "A", t)); t += random.uniform(0.2, 0.6)

    # 1f) UDP DNS + NTP + misc short flows (multiple rounds).
    for _ in range(4):  # 4 rounds
        for client in web_clients:
            for _ in range(random.randint(3, 5)):
                sport = ephemeral; ephemeral += 1
                packets.append(make_udp(client, dns_server, sport, 53, t, payload_len=30)); t += 0.002
                packets.append(make_udp(dns_server, client, 53, sport, t, payload_len=90)); t += random.uniform(0.08, 0.30)
            # NTP
            sport = ephemeral; ephemeral += 1
            packets.append(make_udp(client, ntp_server, sport, 123, t, payload_len=48)); t += 0.002
            packets.append(make_udp(ntp_server, client, 123, sport, t, payload_len=48)); t += random.uniform(0.15, 0.5)
            # Random UDP to varied dst ports (telemetry/log/syslog style)
            for dp in random.sample([514, 1900, 5353, 137, 138, 161, 162, 500, 4500], k=2):
                sport = ephemeral; ephemeral += 1
                packets.append(make_udp(client, monitor, sport, dp, t, payload_len=random.randint(40, 140))); t += random.uniform(0.05, 0.2)

    # 1e) ICMP echo pairs — monitor pinging clients & servers (multiple rounds).
    seq = 1
    for _ in range(10):  # 10 rounds * 15 targets * 2 = 300 ICMP
        for target in web_clients + web_servers:
            packets.append(make_icmp(monitor, target, 8, seq, t)); t += 0.002
            packets.append(make_icmp(target, monitor, 0, seq, t)); t += random.uniform(0.15, 0.45)
            seq += 1

    baseline_end = t

    # -------------------------------------------------------------------
    # 2) Beaconing flow — 15 regular UDP packets every 2.0 ± 0.05 s.
    #    Single 5-tuple: (scanner, monitor, 51515, 4444, UDP).
    # -------------------------------------------------------------------
    beacon_ts = t0 + 5.0  # start near the beginning so it overlaps baseline
    for i in range(15):
        ts = beacon_ts + i * 2.0 + random.uniform(-0.05, 0.05)
        packets.append(make_udp("10.50.9.77", monitor, 51515, 4444, ts, payload_len=16))

    # -------------------------------------------------------------------
    # 3) DoS + port-scan burst concentrated in a single 60 s window.
    #    We place the burst well *after* baseline_end so it occupies its own
    #    minute bucket, which makes peak_minute_rate large relative to others.
    # -------------------------------------------------------------------
    burst_start = baseline_end + 10.0

    # 3a) ARP scan — scanner blasts ARP requests at targets across 3 subnets.
    arp_scan_total = 0
    arp_subnets = ["10.50.8", "10.50.9", "10.50.10"]
    for subnet in arp_subnets:
        for i in range(255):
            target_ip = f"{subnet}.{i + 1}"
            ts = burst_start + arp_scan_total * 0.008  # 0.008 s spacing
            packets.append(make_arp(_mac(scanner), scanner, BROADCAST_MAC, target_ip, 1, ts))
            arp_scan_total += 1
    arp_scan_count = arp_scan_total

    # 3b) TCP SYN-scan — single source, one destination, 150 unique dst ports,
    #     each probed 3 times, SYN-only.  3 * 150 = 450 pkts.
    syn_start = burst_start + arp_scan_count * 0.01 + 0.1
    scan_dst = "10.50.2.10"
    unique_ports = list(range(1, 151))  # 150 unique ports
    syn_count = 0
    for repeat in range(3):
        random.shuffle(unique_ports)
        for i, port in enumerate(unique_ports):
            sport = 33000 + (repeat * 211 + i) % 2000
            ts = syn_start + syn_count * 0.010
            packets.append(make_tcp(scanner, scan_dst, sport, port, "S", ts, payload_len=0))
            syn_count += 1

    # -------------------------------------------------------------------
    # 4) Post-burst low-traffic tail — a long quiet stretch stretches
    #    `span_seconds` out so mean-per-minute falls and dos_spike fires.
    # -------------------------------------------------------------------
    # Tail must stretch span to >~25 min AND keep per-minute rate <<burst so
    # peak/mean ratio exceeds 20.  Add a small number of well-spaced packets.
    tail_start = burst_start + 90.0  # burst ended ~75-80 s in; add margin
    tail_pkts = []
    # 100 pairs over ~50 min tail = ~4 pkts/min — keeps mean-per-minute low so
    # peak_minute_rate / mean_minute_rate > 20 and dos_spike_flag fires.
    tail_count = 100
    tail_step = 30.0
    for i in range(tail_count):
        ts = tail_start + i * tail_step
        client = random.choice(web_clients)
        server = random.choice(web_servers)
        sport = ephemeral; ephemeral += 1
        tail_pkts.append(make_tcp(client, server, sport, 80, "S", ts))
        tail_pkts.append(make_tcp(server, client, 80, sport, "SA", ts + 0.01))
    packets.extend(tail_pkts)

    # -------------------------------------------------------------------
    # Sort by timestamp and write.
    # -------------------------------------------------------------------
    packets.sort(key=lambda p: float(p.time))
    wrpcap(str(out_path), packets)

    # Report summary
    from collections import Counter
    proto = Counter()
    for p in packets:
        if ARP in p:
            proto["arp"] += 1
        elif TCP in p:
            proto["tcp"] += 1
        elif UDP in p:
            proto["udp"] += 1
        elif ICMP in p:
            proto["icmp"] += 1
        else:
            proto["other"] += 1
    total = len(packets)
    print(f"Wrote {out_path} with {total} packets")
    for k, v in proto.most_common():
        print(f"  {k}: {v} ({v/total:.1%})")
    ts_sorted = [float(p.time) for p in packets]
    print(f"span_seconds = {ts_sorted[-1] - ts_sorted[0]:.2f}")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "packets.pcap")
    generate(out)
