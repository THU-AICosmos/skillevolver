#!/bin/bash

# Remediate the Erlang/OTP SSH pre-authentication RCE vulnerability.
#
# The root cause: ssh_connection.erl processes connection-layer messages
# (type >= 80, per RFC 4252 §6) even when the client has NOT yet
# authenticated.  We add a guard clause that disconnects unauthenticated
# clients who send such messages.

SRC_ROOT="/app/workspace/otp_src_27.3.2"

echo "[remediation] Applying security fix via inline editor..."
python3 "$(dirname "$0")/apply_fix.py" "${SRC_ROOT}"
echo "[remediation] Done."
