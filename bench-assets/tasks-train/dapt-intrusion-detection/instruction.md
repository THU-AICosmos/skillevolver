You're given `packets.pcap` (subset of DAPT2020 traffic). You are performing a **network capacity planning audit**. Compute the requested stats and fill in only the `value` column in `/root/capacity_audit.csv`. Lines starting with `#` are comments—leave them.

Bandwidth & Payload
- `total_bytes`: sum of all packet lengths (bytes)
- `avg_packet_size`: mean packet length
- `max_packet_size`: largest packet length

Protocol Breakdown
- `protocol_tcp`: number of TCP packets
- `protocol_arp`: number of ARP packets
- `protocol_ip_total`: packets containing an IP layer

Topology Overview (directed IP graph)
Nodes = IPs; edges = unique (src_ip → dst_ip) pairs.
- `num_nodes`: distinct IPs (src or dst)
- `num_edges`: distinct directed (src,dst) pairs
- `max_outdegree`: max distinct destinations contacted by any single source IP
- `network_density`: `num_edges / (num_nodes * (num_nodes - 1))` (use 0 if `num_nodes < 2`)

Traffic Timing
Sort packets by timestamp.
- `duration_seconds`: last_timestamp − first_timestamp (seconds)
- `iat_mean`: mean inter-arrival time between consecutive packets (seconds)
- `iat_variance`: population variance of inter-arrival times

Capacity Flags (`true`/`false`, based on your computed metrics)
- `is_traffic_benign`: nothing clearly malicious
- `has_beaconing`: periodic communication (low IAT variance, repeatable intervals)
- `has_port_scan`: malicious port scanning
