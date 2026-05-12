"""
Test suite for Apache Druid CVE-2021-26920 vulnerability fix validation.

CVE-2021-26920 is a vulnerability where:
1. The sampler endpoint allows "type": "local" InputSource to read arbitrary files
2. The sampler endpoint allows "type": "http" InputSource for SSRF attacks
3. Authenticated users can exfiltrate sensitive server data

This test sends multiple exploit payloads and verifies they are all blocked.
"""

import os
import subprocess
from pathlib import Path


def test_patches_exist():
    """Test that patch files were created."""
    workspace = os.getenv("WORKSPACE", "/root")
    patches_dir = Path(workspace) / "patches"

    assert patches_dir.exists(), "Patches directory not found"

    patch_files = list(patches_dir.glob("*.patch"))
    assert len(patch_files) > 0, "No patch files found"


def test_patches_applied():
    """Test that patches were applied to the Druid source code."""
    workspace = os.getenv("WORKSPACE", "/root")
    druid_dir = Path(workspace) / "druid"

    assert druid_dir.exists(), "Druid source directory not found"

    result = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=druid_dir,
        capture_output=True,
        text=True,
        timeout=10
    )

    modified_files = [f for f in result.stdout.strip().split("\n") if f]
    assert len(modified_files) > 0, "No files were modified. Patches must be applied."


def get_local_file_read_payloads():
    """
    Generate multiple CVE-2021-26920 exploit payloads targeting local file reads.

    All payloads use the "local" InputSource type to read files from the server
    filesystem. We test with different file paths to ensure the fix blocks
    the input source type itself, not just specific file paths.
    """
    payloads = []

    # Payload 1: Read /etc/passwd
    payloads.append({
        "name": "local_read_etc_passwd",
        "description": "Read /etc/passwd via local InputSource",
        "leak_indicator": "root:",
        "input_source": {
            "type": "local",
            "baseDir": "/etc",
            "filter": "passwd"
        }
    })

    # Payload 2: Read /etc/shadow (sensitive credentials)
    payloads.append({
        "name": "local_read_etc_shadow",
        "description": "Read /etc/shadow via local InputSource",
        "leak_indicator": None,
        "input_source": {
            "type": "local",
            "baseDir": "/etc",
            "filter": "shadow"
        }
    })

    # Payload 3: Read /etc/hostname
    payloads.append({
        "name": "local_read_etc_hostname",
        "description": "Read /etc/hostname via local InputSource",
        "leak_indicator": None,
        "input_source": {
            "type": "local",
            "baseDir": "/etc",
            "filter": "hostname"
        }
    })

    # Payload 4: Read Druid configuration files
    payloads.append({
        "name": "local_read_druid_config",
        "description": "Read Druid runtime properties via local InputSource",
        "leak_indicator": "druid",
        "input_source": {
            "type": "local",
            "baseDir": "/opt/druid/conf/druid/single-server/nano-quickstart",
            "filter": "*.properties"
        }
    })

    # Payload 5: Read /proc/self/environ (environment variables)
    payloads.append({
        "name": "local_read_proc_environ",
        "description": "Read process environment via local InputSource",
        "leak_indicator": None,
        "input_source": {
            "type": "local",
            "baseDir": "/proc/self",
            "filter": "environ"
        }
    })

    return payloads


def get_ssrf_payloads():
    """
    Generate SSRF exploit payloads using HTTP InputSource.

    The HTTP InputSource can be used to probe internal services and
    potentially exfiltrate data via out-of-band requests.
    """
    payloads = []

    # Payload 1: Probe internal metadata service (cloud environments)
    payloads.append({
        "name": "ssrf_metadata_service",
        "description": "Probe cloud metadata service via HTTP InputSource",
        "input_source": {
            "type": "http",
            "uris": ["http://169.254.169.254/latest/meta-data/"]
        }
    })

    # Payload 2: Probe localhost services
    payloads.append({
        "name": "ssrf_localhost_probe",
        "description": "Probe localhost services via HTTP InputSource",
        "input_source": {
            "type": "http",
            "uris": ["http://127.0.0.1:8080/"]
        }
    })

    # Payload 3: Probe internal network
    payloads.append({
        "name": "ssrf_internal_network",
        "description": "Probe internal network via HTTP InputSource",
        "input_source": {
            "type": "http",
            "uris": ["http://10.0.0.1:80/"]
        }
    })

    return payloads


def build_exploit_request(input_source):
    """Build the full exploit request payload with the given InputSource."""
    return {
        "type": "index",
        "spec": {
            "type": "index",
            "ioConfig": {
                "type": "index",
                "inputSource": input_source,
                "inputFormat": {
                    "type": "json"
                }
            },
            "dataSchema": {
                "dataSource": "test",
                "timestampSpec": {
                    "column": "timestamp",
                    "format": "auto"
                },
                "dimensionsSpec": {}
            }
        },
        "samplerConfig": {
            "numRows": 10,
            "timeoutMs": 15000
        }
    }


def test_legitimate_requests_still_work():
    """
    Test that legitimate (inline InputSource) sampler requests still work.

    This ensures the fix doesn't just block the entire endpoint,
    but specifically validates and blocks dangerous InputSource types.
    """
    druid_host = os.getenv("DRUID_HOST", "localhost")
    druid_port = int(os.getenv("DRUID_PORT", "8888"))

    # Legitimate request with inline InputSource (safe)
    legitimate_payload = {
        "type": "index",
        "spec": {
            "type": "index",
            "ioConfig": {
                "type": "index",
                "inputSource": {
                    "type": "inline",
                    "data": '{"timestamp":"2021-01-01T00:00:00Z","value":"test"}'
                },
                "inputFormat": {
                    "type": "json"
                }
            },
            "dataSchema": {
                "dataSource": "test",
                "timestampSpec": {
                    "column": "timestamp",
                    "format": "auto"
                },
                "dimensionsSpec": {}
            }
        },
        "samplerConfig": {
            "numRows": 10,
            "timeoutMs": 15000
        }
    }

    try:
        import requests

        url = f"http://{druid_host}:{druid_port}/druid/indexer/v1/sampler"

        response = requests.post(
            url,
            json=legitimate_payload,
            headers={"Content-Type": "application/json"},
            timeout=20
        )

        response_text = response.text.lower()

        # Check if it was incorrectly blocked
        incorrectly_blocked = (
            "local" in response_text and (
                "blocked" in response_text or
                "not allowed" in response_text or
                "forbidden" in response_text
            )
        ) or (
            "inputsource" in response_text and (
                "blocked" in response_text or
                "not allowed" in response_text
            )
        )

        assert not incorrectly_blocked, (
            f"Legitimate inline request was incorrectly blocked! "
            f"Status: {response.status_code}, Response: {response.text[:300]}"
        )

        print(f"  Legitimate request handled correctly (status: {response.status_code})")

    except requests.exceptions.ConnectionError:
        assert False, (
            f"Cannot connect to Druid server at {druid_host}:{druid_port}. "
            "The patched Druid must be running."
        )


def test_cve_2021_26920_local_file_reads_blocked():
    """
    DEFINITIVE TEST: Send multiple local file read exploit variants and verify ALL are blocked.

    CVE-2021-26920 allows authenticated users to use the sampler endpoint with
    "type": "local" InputSource to read arbitrary files from the server filesystem.

    We test with multiple different file paths to ensure the fix blocks
    the dangerous InputSource type itself, not just specific paths.
    """
    druid_host = os.getenv("DRUID_HOST", "localhost")
    druid_port = int(os.getenv("DRUID_PORT", "8888"))

    exploit_payloads = get_local_file_read_payloads()
    failed_exploits = []
    blocked_exploits = []

    try:
        import requests

        url = f"http://{druid_host}:{druid_port}/druid/indexer/v1/sampler"

        for payload_info in exploit_payloads:
            exploit_request = build_exploit_request(payload_info["input_source"])

            try:
                response = requests.post(
                    url,
                    json=exploit_request,
                    headers={"Content-Type": "application/json"},
                    timeout=20
                )

                response_text = response.text.lower()

                # Check if file contents were leaked
                leak_detected = False
                if response.status_code == 200:
                    if payload_info.get("leak_indicator"):
                        if payload_info["leak_indicator"].lower() in response_text:
                            leak_detected = True

                    # Generic indicators of successful file read
                    if "numrowsread" in response_text and "data" in response_text:
                        leak_detected = True

                if leak_detected:
                    failed_exploits.append({
                        "name": payload_info["name"],
                        "reason": f"FILE READ SUCCEEDED! Data found in response: {response.text[:200]}"
                    })
                    continue

                # Check if properly blocked
                is_blocked = (
                    response.status_code >= 400 or
                    "not allowed" in response_text or
                    "blocked" in response_text or
                    "forbidden" in response_text or
                    "security" in response_text or
                    "exception" in response_text or
                    "error" in response_text or
                    "disabled" in response_text or
                    "rejected" in response_text or
                    "illegal" in response_text or
                    "cve-2021-26920" in response_text or
                    "local" in response_text and "not" in response_text
                )

                if is_blocked:
                    blocked_exploits.append(payload_info["name"])
                else:
                    # Unclear but no data leaked - treat as blocked
                    blocked_exploits.append(payload_info["name"])

            except requests.exceptions.Timeout:
                failed_exploits.append({
                    "name": payload_info["name"],
                    "reason": "Request timed out - exploit may be executing"
                })

        # Report results
        print(f"\n  Blocked local file read exploits ({len(blocked_exploits)}/{len(exploit_payloads)}):")
        for name in blocked_exploits:
            print(f"  - {name}")

        if failed_exploits:
            print(f"\n  FAILED local file read exploits ({len(failed_exploits)}):")
            for f in failed_exploits:
                print(f"  - {f['name']}: {f['reason']}")

        assert len(failed_exploits) == 0, (
            f"CVE-2021-26920 fix incomplete! {len(failed_exploits)} local file read exploits not blocked: "
            f"{[f['name'] for f in failed_exploits]}"
        )

        print(f"\n  All {len(exploit_payloads)} local file read exploit variants blocked!")

    except requests.exceptions.ConnectionError:
        assert False, (
            f"Cannot connect to Druid server at {druid_host}:{druid_port}. "
            "The patched Druid must be built and running to verify the fix. "
            "Start Druid with: cd /root/druid && ./bin/start-single-server-small"
        )


def test_cve_2021_26920_ssrf_attacks_blocked():
    """
    Test that HTTP InputSource SSRF attacks are also blocked.

    The same vulnerability class allows SSRF via "type": "http" InputSource,
    enabling attackers to probe internal network services.
    """
    druid_host = os.getenv("DRUID_HOST", "localhost")
    druid_port = int(os.getenv("DRUID_PORT", "8888"))

    ssrf_payloads = get_ssrf_payloads()
    failed_exploits = []
    blocked_exploits = []

    try:
        import requests

        url = f"http://{druid_host}:{druid_port}/druid/indexer/v1/sampler"

        for payload_info in ssrf_payloads:
            exploit_request = build_exploit_request(payload_info["input_source"])

            try:
                response = requests.post(
                    url,
                    json=exploit_request,
                    headers={"Content-Type": "application/json"},
                    timeout=20
                )

                response_text = response.text.lower()

                # Check if properly blocked
                is_blocked = (
                    response.status_code >= 400 or
                    "not allowed" in response_text or
                    "blocked" in response_text or
                    "forbidden" in response_text or
                    "security" in response_text or
                    "exception" in response_text or
                    "error" in response_text or
                    "disabled" in response_text or
                    "rejected" in response_text or
                    "illegal" in response_text or
                    "cve-2021-26920" in response_text or
                    "http" in response_text and "not" in response_text
                )

                # Check if SSRF succeeded (got actual response data back)
                ssrf_succeeded = (
                    response.status_code == 200 and
                    "numrowsread" in response_text and
                    "data" in response_text
                )

                if ssrf_succeeded and not is_blocked:
                    failed_exploits.append({
                        "name": payload_info["name"],
                        "reason": f"SSRF succeeded! Got response data: {response.text[:200]}"
                    })
                elif is_blocked:
                    blocked_exploits.append(payload_info["name"])
                else:
                    # Connection timeout/error on SSRF target is expected - treat as blocked
                    blocked_exploits.append(payload_info["name"])

            except requests.exceptions.Timeout:
                # Timeout could mean SSRF is being attempted
                failed_exploits.append({
                    "name": payload_info["name"],
                    "reason": "Request timed out - SSRF may be in progress"
                })

        # Report results
        print(f"\n  Blocked SSRF exploits ({len(blocked_exploits)}/{len(ssrf_payloads)}):")
        for name in blocked_exploits:
            print(f"  - {name}")

        if failed_exploits:
            print(f"\n  FAILED SSRF exploits ({len(failed_exploits)}):")
            for f in failed_exploits:
                print(f"  - {f['name']}: {f['reason']}")

        assert len(failed_exploits) == 0, (
            f"CVE-2021-26920 SSRF fix incomplete! {len(failed_exploits)} SSRF exploits not blocked: "
            f"{[f['name'] for f in failed_exploits]}"
        )

        print(f"\n  All {len(ssrf_payloads)} SSRF exploit variants blocked!")

    except requests.exceptions.ConnectionError:
        assert False, (
            f"Cannot connect to Druid server at {druid_host}:{druid_port}. "
            "The patched Druid must be built and running to verify the fix."
        )
