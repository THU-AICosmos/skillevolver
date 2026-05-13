"""Verifier tests for the Suricata C2 beacon detection task.

The verifier runs Suricata offline against training PCAPs and generated PCAPs,
and checks whether `sid:1000001` is (or is not) raised.

Test count note:
We intentionally keep individual test items (no parametrisation) so pytest and CTRF both report 14 tests total.
"""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from scapy.all import IP, TCP, Ether, Raw, wrpcap

ALERT_SID = 1000001
PCAP_ROOT = Path("/root/pcaps")
SURI_CFG = Path("/root/suricata.yaml")
RULES = Path("/root/local.rules")


@dataclass(frozen=True)
class Scenario:
    label: str
    raw_request: bytes
    expect_alert: bool


def _exec(argv: list[str], *, tmo: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=tmo)


def _assemble_session(pcap_dst: Path, src_ip: str, dst_ip: str, *, src_port: int, dst_port: int, http_bytes: bytes) -> None:
    """Craft a minimal TCP session containing one HTTP request + response."""
    c_isn = 30000
    s_isn = 40000

    e = Ether(src="02:aa:bb:cc:00:01", dst="02:aa:bb:cc:00:02")
    ip_fwd = IP(src=src_ip, dst=dst_ip)
    ip_rev = IP(src=dst_ip, dst=src_ip)

    syn = e / ip_fwd / TCP(sport=src_port, dport=dst_port, flags="S", seq=c_isn)
    sa = e / ip_rev / TCP(sport=dst_port, dport=src_port, flags="SA", seq=s_isn, ack=c_isn + 1)
    a0 = e / ip_fwd / TCP(sport=src_port, dport=dst_port, flags="A", seq=c_isn + 1, ack=s_isn + 1)

    boundary = http_bytes.find(b"\r\n\r\n")
    if boundary != -1:
        c1 = max(1, boundary // 2)
        c2 = min(len(http_bytes) - 1, boundary + 4 + 12)
        segments = [http_bytes[:c1], http_bytes[c1:c2], http_bytes[c2:]]
    else:
        c1 = max(1, len(http_bytes) // 3)
        c2 = max(c1 + 1, (2 * len(http_bytes)) // 3)
        segments = [http_bytes[:c1], http_bytes[c1:c2], http_bytes[c2:]]

    data_frames = []
    cur_seq = c_isn + 1
    for seg in segments:
        if not seg:
            continue
        data_frames.append(e / ip_fwd / TCP(sport=src_port, dport=dst_port, flags="PA", seq=cur_seq, ack=s_isn + 1) / Raw(load=seg))
        cur_seq += len(seg)

    payload_len = sum(len(s) for s in segments)
    a1 = e / ip_rev / TCP(sport=dst_port, dport=src_port, flags="A", seq=s_isn + 1, ack=c_isn + 1 + payload_len)

    reply = b"HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n"
    rp = (
        e / ip_rev
        / TCP(sport=dst_port, dport=src_port, flags="PA", seq=s_isn + 1, ack=c_isn + 1 + payload_len)
        / Raw(load=reply)
    )
    rlen = len(reply)
    a2 = e / ip_fwd / TCP(sport=src_port, dport=dst_port, flags="A", seq=c_isn + 1 + payload_len, ack=s_isn + 1 + rlen)
    f1 = e / ip_fwd / TCP(sport=src_port, dport=dst_port, flags="FA", seq=c_isn + 1 + payload_len, ack=s_isn + 1 + rlen)
    f2 = e / ip_rev / TCP(sport=dst_port, dport=src_port, flags="FA", seq=s_isn + 1 + rlen, ack=c_isn + 2 + payload_len)
    a3 = e / ip_fwd / TCP(sport=src_port, dport=dst_port, flags="A", seq=c_isn + 2 + payload_len, ack=s_isn + 2 + rlen)

    wrpcap(str(pcap_dst), [syn, sa, a0, *data_frames, a1, rp, a2, f1, f2, a3])


def _extract_alert_sids(eve: Path) -> list[int]:
    found: list[int] = []
    if not eve.exists():
        return found
    for line in eve.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("event_type") != "alert":
            continue
        a = obj.get("alert") or {}
        sid = a.get("signature_id")
        if isinstance(sid, int):
            found.append(sid)
    return found


def _suricata_check(pcap: Path, logdir: Path) -> list[int]:
    if logdir.exists():
        shutil.rmtree(logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "suricata", "--runmode", "single",
        "-c", str(SURI_CFG),
        "-S", str(RULES),
        "-k", "none",
        "-r", str(pcap),
        "-l", str(logdir),
    ]
    proc = _exec(cmd, tmo=180)
    assert proc.returncode == 0, f"Suricata error on {pcap.name}:\n{proc.stdout}\n{proc.stderr}"
    return _extract_alert_sids(logdir / "eve.json")


def _compose_request(verb: str, uri: str, *, hdrs: dict[str, str], body: bytes) -> bytes:
    all_hdrs = {
        "Content-Length": str(len(body)),
        "Connection": "close",
        **hdrs,
    }
    hdr_bytes = b"\r\n".join([f"{k}: {v}".encode() for k, v in all_hdrs.items()])
    return b"".join([
        f"{verb} {uri} HTTP/1.1\r\n".encode(),
        b"Host: healthapi.internal\r\n",
        hdr_bytes,
        b"\r\n\r\n",
        body,
    ])


def _seeded_hex(count: int, *, seed: int) -> str:
    import random
    rng = random.Random(seed)
    return "".join(rng.choice("0123456789abcdef") for _ in range(count))


def _good_scenarios() -> list[Scenario]:
    chk_a = _seeded_hex(40, seed=10)
    chk_b = _seeded_hex(40, seed=20)
    chk_c = _seeded_hex(40, seed=30)
    chk_d = _seeded_hex(40, seed=40)
    data_long = _seeded_hex(140, seed=10)
    data_med = _seeded_hex(120, seed=20)
    data_exact = _seeded_hex(100, seed=30)
    data_big = _seeded_hex(200, seed=40)

    h1 = {"x-beacon-type": "command", "Content-Type": "application/x-www-form-urlencoded"}
    h2 = {"X-Beacon-Type": "  command", "Content-Type": "application/x-www-form-urlencoded"}
    h3 = {"X-BEACON-TYPE": "command", "Content-Type": "application/x-www-form-urlencoded"}
    h4 = {"X-Beacon-type": "command", "Content-Type": "application/x-www-form-urlencoded"}

    b1 = f"ts=1680000&data={data_long}&node=w1&checksum={chk_a}&seq=1".encode()
    b2 = f"checksum={chk_b}&data={data_med}&ts=9999".encode()
    b3 = f"data={data_exact}&checksum={chk_c}".encode()
    b4 = f"id=abc&data={data_big}&x=y&checksum={chk_d}&z=0".encode()

    return [
        Scenario("synth_hit_1", _compose_request("PUT", "/api/v3/heartbeat", hdrs=h1, body=b1), True),
        Scenario("synth_hit_2", _compose_request("PUT", "/api/v3/heartbeat", hdrs=h2, body=b2), True),
        Scenario("synth_hit_3", _compose_request("PUT", "/api/v3/heartbeat", hdrs=h3, body=b3), True),
        Scenario("synth_hit_4", _compose_request("PUT", "/api/v3/heartbeat", hdrs=h4, body=b4), True),
    ]


def _bad_scenarios() -> list[Scenario]:
    chk_ok = _seeded_hex(40, seed=10)
    data_ok = _seeded_hex(140, seed=10)
    data_short = _seeded_hex(50, seed=50)

    h_cmd = {"X-Beacon-Type": "command", "Content-Type": "application/x-www-form-urlencoded"}
    h_status = {"X-Beacon-Type": "status", "Content-Type": "application/x-www-form-urlencoded"}

    body_ok = f"data={data_ok}&checksum={chk_ok}".encode()
    body_short_data = f"data={data_short}&checksum={chk_ok}".encode()
    body_no_checksum = f"data={data_ok}".encode()
    # checksum embedded in a value, not as a top-level param key
    body_chk_in_val = f"note=checksum={chk_ok}&data={data_ok}".encode()
    # Wrong checksum length (32 instead of 40)
    short_chk = _seeded_hex(32, seed=60)
    body_wrong_chk_len = f"data={data_ok}&checksum={short_chk}".encode()

    return [
        # Wrong header value
        Scenario("synth_miss_wrong_hdr", _compose_request("PUT", "/api/v3/heartbeat", hdrs=h_status, body=body_ok), False),
        # Data too short
        Scenario("synth_miss_short_data", _compose_request("PUT", "/api/v3/heartbeat", hdrs=h_cmd, body=body_short_data), False),
        # Missing checksum
        Scenario("synth_miss_no_checksum", _compose_request("PUT", "/api/v3/heartbeat", hdrs=h_cmd, body=body_no_checksum), False),
        # checksum inside value
        Scenario("synth_miss_chk_in_val", _compose_request("PUT", "/api/v3/heartbeat", hdrs=h_cmd, body=body_chk_in_val), False),
        # GET instead of PUT
        Scenario("synth_miss_get", _compose_request("GET", f"/api/v3/heartbeat?data={data_ok}&checksum={chk_ok}", hdrs=h_cmd, body=b""), False),
        # Wrong checksum length
        Scenario("synth_miss_wrong_chk_len", _compose_request("PUT", "/api/v3/heartbeat", hdrs=h_cmd, body=body_wrong_chk_len), False),
    ]


def _evaluate_scenario(sc: Scenario, *, work: Path, idx: int) -> None:
    pcap = work / f"{sc.label}.pcap"
    _assemble_session(
        pcap,
        src_ip="192.168.1.10",
        dst_ip="192.168.1.20",
        src_port=15000 + idx,
        dst_port=9090,
        http_bytes=sc.raw_request,
    )
    sids = _suricata_check(pcap, work / f"log_{sc.label}")
    triggered = ALERT_SID in sids
    assert triggered == sc.expect_alert, f"{sc.label}: expected_alert={sc.expect_alert} got_sids={sids}"


class TestFilePresence:
    def test_training_pcaps_present(self):
        assert (PCAP_ROOT / "train_pos.pcap").exists()
        assert (PCAP_ROOT / "train_neg.pcap").exists()


class TestTrainingCaptures:
    def test_pos_capture_triggers(self, tmp_path: Path):
        sids = _suricata_check(PCAP_ROOT / "train_pos.pcap", tmp_path / "log_tpos")
        assert ALERT_SID in sids, f"Expected sid {ALERT_SID} in train_pos.pcap; got {sids}"

    def test_neg_capture_silent(self, tmp_path: Path):
        sids = _suricata_check(PCAP_ROOT / "train_neg.pcap", tmp_path / "log_tneg")
        assert ALERT_SID not in sids, f"Unexpected sid {ALERT_SID} in train_neg.pcap; got {sids}"


class TestSynthesisedCaptures:
    def test_hit_1(self, tmp_path: Path):
        _evaluate_scenario(_good_scenarios()[0], work=tmp_path, idx=1)

    def test_hit_2(self, tmp_path: Path):
        _evaluate_scenario(_good_scenarios()[1], work=tmp_path, idx=2)

    def test_hit_3(self, tmp_path: Path):
        _evaluate_scenario(_good_scenarios()[2], work=tmp_path, idx=3)

    def test_hit_4(self, tmp_path: Path):
        _evaluate_scenario(_good_scenarios()[3], work=tmp_path, idx=4)

    def test_miss_1(self, tmp_path: Path):
        _evaluate_scenario(_bad_scenarios()[0], work=tmp_path, idx=5)

    def test_miss_2(self, tmp_path: Path):
        _evaluate_scenario(_bad_scenarios()[1], work=tmp_path, idx=6)

    def test_miss_3(self, tmp_path: Path):
        _evaluate_scenario(_bad_scenarios()[2], work=tmp_path, idx=7)

    def test_miss_4(self, tmp_path: Path):
        _evaluate_scenario(_bad_scenarios()[3], work=tmp_path, idx=8)

    def test_miss_5(self, tmp_path: Path):
        _evaluate_scenario(_bad_scenarios()[4], work=tmp_path, idx=9)

    def test_miss_6(self, tmp_path: Path):
        _evaluate_scenario(_bad_scenarios()[5], work=tmp_path, idx=10)


class TestRuleSanity:
    def test_rule_contains_required_keywords(self):
        txt = RULES.read_text(errors="replace")
        assert re.search(r"sid\s*:\s*1000001", txt), "Rule must include sid:1000001"
        assert "http.method" in txt or "http_method" in txt
        assert "http.uri" in txt or "http_uri" in txt
        assert "http.header" in txt or "http_header" in txt
        assert ("http_client_body" in txt) or ("http.request_body" in txt) or ("http_request_body" in txt)
