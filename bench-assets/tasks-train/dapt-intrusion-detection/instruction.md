A packet capture of a cloud-tenant web service is waiting at `/root/packets.pcap`. Work through the sections below, compute each statistic, and write the answer into the `value` column of `/root/network_analysis.csv`. Section-header rows start with `#` — leave them unchanged.

### Volume and Protocol Mix

- `frame_count`: total frames in the capture.
- `tcp_packet_count`: frames carrying a TCP segment.
- `udp_packet_count`: frames carrying a UDP segment.
- `icmp_packet_count`: frames carrying an ICMP message.
- `protocol_arp`: frames carrying an ARP message.
- `protocol_ip_total`: frames that contain any IP layer.
- `dominant_protocol`: lowercase name of the most-common protocol among
  `{tcp, udp, icmp, arp}`. Break ties with priority `tcp > udp > icmp > arp`.

### Byte Counters and Frame Sizes

- `total_octets`: sum of every frame length (bytes).
- `mean_frame_length`: arithmetic mean of frame lengths.
- `smallest_frame`: minimum frame length.
- `largest_frame`: maximum frame length.

### Capture Rate

Sort packets by timestamp, then bucket them into consecutive 60-second windows starting at the earliest timestamp.

- `capture_span_seconds`: last_timestamp − first_timestamp.
- `peak_minute_rate`: largest per-bucket packet count.
- `mean_minute_rate`: mean of the per-bucket counts.
- `floor_minute_rate`: smallest per-bucket count.

### Endpoint Diversity (Shannon entropy, log base 2)

Define `H(X) = -sum(p_i * log2(p_i))` over the empirical frequency distribution.

- `dest_port_entropy` and `source_port_entropy`: entropy of destination / source ports across TCP+UDP.
- `source_ip_entropy` and `dest_ip_entropy`: entropy of source / destination IP addresses across IP packets.
- `unique_dest_ports` and `unique_source_ports`: distinct TCP+UDP destination / source port numbers observed.

### Conversation Graph (directed IP graph)

Treat every unique `(src_ip → dst_ip)` pair as one directed edge between IP nodes.

- `host_count`: distinct IPs appearing as source or destination.
- `conversation_edges`: distinct `(src, dst)` pairs.
- `graph_density`: `conversation_edges / (host_count * (host_count - 1))` (use 0 when `host_count < 2`).
- `max_fanout`: largest number of distinct destinations reached by any single source IP.
- `max_fanin`: largest number of distinct sources contacting any single destination IP.

### Inter-Arrival and Role Analysis

- `interarrival_mean`, `interarrival_variance`: mean and population variance of gaps between consecutive (timestamp-sorted) packets.
- `interarrival_cv`: coefficient of variation (std / mean) of inter-arrival times; use 0 if the mean is 0.
- Producer / Consumer Ratio per IP:
  - `bytes_sent` = sum of frame lengths where the IP is source.
  - `bytes_recv` = sum of frame lengths where the IP is destination.
  - `PCR = (bytes_sent - bytes_recv) / (bytes_sent + bytes_recv)` when the denominator is non-zero.
- `producer_hosts`: count of IPs with `PCR > 0.2`.
- `consumer_hosts`: count of IPs with `PCR < -0.2`.

### 5-Tuple Flow Enumeration

Define a flow by the tuple `(src_ip, dst_ip, src_port, dst_port, protocol)` for TCP and UDP traffic.

- `distinct_flows`: count of distinct 5-tuples.
- `tcp_flow_count`, `udp_flow_count`: distinct 5-tuples whose protocol is TCP / UDP.
- `paired_flows`: distinct flow pairs whose mirror tuple `(dst_ip, src_ip, dst_port, src_port, protocol)` also appears in the capture (count each pair once).

### Threat Indicators

Report each flag as the lowercase string `true` or `false`, based on your own computed values:

- `benign_traffic_flag`: whether the traffic looks benign overall (i.e. none of the red-flag heuristics below fire).
- `port_scan_flag`: whether any source IP aggressively probes many destination ports (high port-entropy, high SYN-only ratio, sufficient volume, >100 unique dst ports).
- `dos_spike_flag`: whether the capture contains a flood-like throughput spike — `peak_minute_rate / mean_minute_rate` exceeds ~20.
- `beaconing_flag`: whether any 5-tuple flow shows periodic / robotic timing (coefficient of variation of that flow's inter-arrival times below ~0.5 with at least 5 packets).
