"""
Verification tests for the Erlang/OTP SSH pre-auth RCE mitigation.

Tests:
  1. Legitimate SSH session with password auth still works
  2. Authenticated command execution returns expected output
  3. Pre-auth exploit is blocked (cannot create marker directory)
"""

import os
import socket
import subprocess
import time

import paramiko
import pytest

_COMPILATION_DONE = False

DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = 3333
SSH_USER = "admin"
SSH_PASS = "s3cure_pass"
SSHD_LOG = "/tmp/sshd_output.log"
MARKER_DIR = "/tmp/pwned"


def _tail_bytes(filepath: str, nbytes: int = 20000) -> str:
    try:
        with open(filepath, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            total = fh.tell()
            fh.seek(max(0, total - nbytes), os.SEEK_SET)
            return fh.read().decode(errors="replace")
    except FileNotFoundError:
        return f"<missing: {filepath}>"


def _compile_and_launch() -> None:
    """Run the build/launch script exactly once per pytest session."""
    global _COMPILATION_DONE
    if _COMPILATION_DONE:
        return

    logfile = "/tmp/compilation.log"
    result = subprocess.run(
        [
            "bash", "-lc",
            f"set -o pipefail; chmod +x /tests/build.sh; /tests/build.sh 2>&1 | tee {logfile}",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=1500,
    )
    assert result.returncode == 0, (
        "Compilation/launch script failed: /tests/build.sh\n"
        f"exit code: {result.returncode}\n"
        f"--- tail({logfile}) ---\n{_tail_bytes(logfile)}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\n"
    )

    _COMPILATION_DONE = True
    _await_tcp(DAEMON_HOST, DAEMON_PORT, wait_sec=60.0)


@pytest.fixture(scope="session", autouse=True)
def _setup_erlang_sshd() -> None:
    """Session-scoped fixture: compile OTP and start SSH daemon before all tests."""
    _compile_and_launch()


def _await_tcp(host: str, port: int, wait_sec: float = 30.0) -> None:
    end_time = time.time() + wait_sec
    err = None
    while time.time() < end_time:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except Exception as e:
            err = e
            time.sleep(0.25)
    raise AssertionError(f"TCP {host}:{port} unreachable after {wait_sec}s. Last: {err!r}")


def _log_snippet(filepath: str, nbytes: int = 4000) -> str:
    try:
        with open(filepath, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            sz = fh.tell()
            fh.seek(max(0, sz - nbytes), os.SEEK_SET)
            return fh.read().decode(errors="replace")
    except FileNotFoundError:
        return f"<missing: {filepath}>"


def _dir_listing(directory: str = "/tmp") -> str:
    try:
        r = subprocess.run(
            ["bash", "-lc", f"ls -la {directory}"],
            capture_output=True, text=True, check=False, timeout=5,
        )
        return f"exit={r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}\n"
    except Exception as exc:
        return f"<listing failed: {exc!r}>"


# ── Test 1: Legitimate authentication ──────────────────────────

def test_legitimate_ssh_session():
    """Verify that password-based SSH login and authenticated exec still work after the fix."""

    # Part A: basic connection
    print(f"[*] [Part A] Connecting as {SSH_USER} to {DAEMON_HOST}:{DAEMON_PORT}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(DAEMON_HOST, port=DAEMON_PORT, username=SSH_USER, password=SSH_PASS, timeout=5)
        tp = ssh.get_transport()
        assert tp is not None and tp.is_active(), (
            "Transport inactive after connect.\n"
            f"--- tail({SSHD_LOG}) ---\n{_log_snippet(SSHD_LOG)}"
        )
        print("[+] [Part A] Authenticated successfully, transport is active.")
    finally:
        ssh.close()

    # Part B: exec command
    exec_cmd = 'os:cmd("echo hello_from_admin").'
    print(f"[*] [Part B] Running authenticated exec: {exec_cmd}")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(DAEMON_HOST, port=DAEMON_PORT, username=SSH_USER, password=SSH_PASS, timeout=5)
        _, out, err = ssh.exec_command(exec_cmd)
        stdout_text = out.read().decode().strip()
        stderr_text = err.read().decode().strip()
        print(f"[*] [Part B] stdout={stdout_text!r} stderr={stderr_text!r}")
        assert stdout_text == "hello_from_admin", (
            f"Unexpected exec output.\n"
            f"Command: {exec_cmd}\n"
            f"stdout: {stdout_text!r}\nstderr: {stderr_text!r}\n"
            f"--- tail({SSHD_LOG}) ---\n{_log_snippet(SSHD_LOG)}"
        )
    finally:
        ssh.close()


# ── Test 2: Pre-auth exploit must be blocked ───────────────────

def test_preauth_exploit_blocked():
    """Run the pre-auth exploit and verify it cannot create the marker directory."""

    # Ensure clean state
    subprocess.run(["rm", "-rf", MARKER_DIR], check=False)

    proc = subprocess.run(
        [
            "python3", "/tests/exploit.py",
            "-t", DAEMON_HOST,
            "-p", str(DAEMON_PORT),
            "-c", f"mkdir -p {MARKER_DIR}",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )

    print(
        f"[*] [Exploit] exit={proc.returncode} "
        f"stdout_len={len(proc.stdout)} stderr_len={len(proc.stderr)}"
    )
    print(f"--- /tmp listing ---\n{_dir_listing()}")

    assert not os.path.isdir(MARKER_DIR), (
        f"Exploit succeeded — {MARKER_DIR} was created!\n"
        f"exit: {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}\n"
    )


# ── Test 0: Print build log ───────────────────────────────────

def test_00_compilation_log():
    """Emit the build script output for debugging visibility."""
    logfile = "/tmp/compilation.log"
    print(f"--- /tests/build.sh output (tail) from {logfile} ---\n{_tail_bytes(logfile)}")
