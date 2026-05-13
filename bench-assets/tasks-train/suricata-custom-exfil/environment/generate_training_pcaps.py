import argparse
import random
from pathlib import Path

from scapy.all import IP, TCP, Ether, Raw, wrpcap


def rand_hex(length: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("0123456789abcdef") for _ in range(length))


def craft_http(method: str, uri: str, hdrs: dict[str, str], payload: bytes) -> bytes:
    computed_hdrs = {
        "Content-Length": str(len(payload)),
        "Connection": "close",
        **hdrs,
    }
    hdr_block = b"\r\n".join([f"{k}: {v}".encode() for k, v in computed_hdrs.items()])
    return b"".join(
        [
            f"{method} {uri} HTTP/1.1\r\n".encode(),
            b"Host: healthapi.internal\r\n",
            hdr_block,
            b"\r\n",
            b"\r\n",
            payload,
        ]
    )


def emit_pcap(dst: Path, http_req: bytes, *, sport: int) -> None:
    cli_ip, srv_ip = "192.168.1.10", "192.168.1.20"
    dport = 9090
    c_seq, s_seq = 50000, 60000

    eth = Ether(src="aa:bb:cc:dd:ee:01", dst="aa:bb:cc:dd:ee:02")
    ip_out = IP(src=cli_ip, dst=srv_ip)
    ip_in = IP(src=srv_ip, dst=cli_ip)

    syn = eth / ip_out / TCP(sport=sport, dport=dport, flags="S", seq=c_seq)
    sa = eth / ip_in / TCP(sport=dport, dport=sport, flags="SA", seq=s_seq, ack=c_seq + 1)
    ack0 = eth / ip_out / TCP(sport=sport, dport=dport, flags="A", seq=c_seq + 1, ack=s_seq + 1)

    hdr_end = http_req.find(b"\r\n\r\n")
    if hdr_end != -1:
        s1 = max(1, hdr_end // 2)
        s2 = min(len(http_req) - 1, hdr_end + 4 + 10)
        parts = [http_req[:s1], http_req[s1:s2], http_req[s2:]]
    else:
        s1 = max(1, len(http_req) // 3)
        s2 = max(s1 + 1, (2 * len(http_req)) // 3)
        parts = [http_req[:s1], http_req[s1:s2], http_req[s2:]]

    data_pkts = []
    sq = c_seq + 1
    for part in parts:
        if not part:
            continue
        data_pkts.append(eth / ip_out / TCP(sport=sport, dport=dport, flags="PA", seq=sq, ack=s_seq + 1) / Raw(load=part))
        sq += len(part)

    total = sum(len(p) for p in parts)
    ack1 = eth / ip_in / TCP(sport=dport, dport=sport, flags="A", seq=s_seq + 1, ack=c_seq + 1 + total)

    resp = b"HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n"
    resp_pkt = eth / ip_in / TCP(sport=dport, dport=sport, flags="PA", seq=s_seq + 1, ack=c_seq + 1 + total) / Raw(load=resp)

    rlen = len(resp)
    ack2 = eth / ip_out / TCP(sport=sport, dport=dport, flags="A", seq=c_seq + 1 + total, ack=s_seq + 1 + rlen)
    fin = eth / ip_out / TCP(sport=sport, dport=dport, flags="FA", seq=c_seq + 1 + total, ack=s_seq + 1 + rlen)
    fa = eth / ip_in / TCP(sport=dport, dport=sport, flags="FA", seq=s_seq + 1 + rlen, ack=c_seq + 2 + total)
    la = eth / ip_out / TCP(sport=sport, dport=dport, flags="A", seq=c_seq + 2 + total, ack=s_seq + 2 + rlen)

    wrpcap(str(dst), [syn, sa, ack0, *data_pkts, ack1, resp_pkt, ack2, fin, fa, la])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    hex_data = rand_hex(120, seed=99)
    chk = rand_hex(40, seed=99)

    hdrs_cmd = {"x-beacon-type": "command", "Content-Type": "application/x-www-form-urlencoded"}
    hdrs_status = {"x-beacon-type": "status", "Content-Type": "application/x-www-form-urlencoded"}

    body_pos = f"ts=1680000000&data={hex_data}&node=worker-7&checksum={chk}&seq=42".encode()
    body_neg = f"ts=1680000000&data={hex_data}&node=worker-7&checksum={chk}&seq=42".encode()

    req_pos = craft_http("PUT", "/api/v3/heartbeat", hdrs_cmd, body_pos)
    req_neg = craft_http("PUT", "/api/v3/heartbeat", hdrs_status, body_neg)

    emit_pcap(out / "train_pos.pcap", req_pos, sport=34567)
    emit_pcap(out / "train_neg.pcap", req_neg, sport=34568)


if __name__ == "__main__":
    main()
