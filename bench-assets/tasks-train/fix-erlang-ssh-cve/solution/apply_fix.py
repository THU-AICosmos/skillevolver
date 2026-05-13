#!/usr/bin/env python3
"""
Inline editor that patches ssh_connection.erl to reject connection-layer
messages from unauthenticated SSH clients (RFC 4252 §6).
"""

import os
import sys


def main():
    otp_root = sys.argv[1]
    target = os.path.join(otp_root, "lib", "ssh", "src", "ssh_connection.erl")

    with open(target, "r") as fh:
        lines = fh.readlines()

    out = []
    logger_inserted = False
    guard_inserted = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # 1. Add logger include after ssh_transport.hrl include
        if not logger_inserted and '-include("ssh_transport.hrl").' in line:
            out.append(line)
            out.append('-include_lib("kernel/include/logger.hrl").\n')
            logger_inserted = True
            i += 1
            continue

        # 2. Insert new clauses right before the first handle_msg for channel_open_confirmation
        if (not guard_inserted and
                line.strip().startswith('handle_msg(#ssh_msg_channel_open_confirmation')):
            out.append(
                'handle_msg(#ssh_msg_disconnect{code = Code, description = Description}, Connection, _, _SSH) ->\n'
                '    {disconnect, {Code, Description}, handle_stop(Connection)};\n'
                '\n'
                'handle_msg(Msg, Connection, server, Ssh = #ssh{authenticated = false}) ->\n'
                '    %% RFC 4252 Section 6: message numbers >= 80 are reserved for the\n'
                '    %% connection protocol and MUST NOT be processed before authentication.\n'
                '    %% Disconnect immediately to prevent pre-auth command execution.\n'
                '    MsgFun = fun(M) ->\n'
                '                     MaxLogItemLen = ?GET_OPT(max_log_item_len, Ssh#ssh.opts),\n'
                '                     io_lib:format("Rejecting connection-layer message from unauthenticated peer."\n'
                '                                   " Message:  ~w", [M],\n'
                '                                   [{chars_limit, MaxLogItemLen}])\n'
                '             end,\n'
                '    ?LOG_DEBUG(MsgFun, [Msg]),\n'
                '    {disconnect, {?SSH_DISCONNECT_PROTOCOL_ERROR, "Connection refused"}, handle_stop(Connection)};\n'
                '\n'
            )
            guard_inserted = True
            out.append(line)
            i += 1
            continue

        # 3. Remove the old disconnect handler at the end of handle_msg clauses
        #    Detect: handle_msg(#ssh_msg_disconnect{code = Code,
        if 'handle_msg(#ssh_msg_disconnect{code = Code,' in line:
            # Skip this clause entirely (it spans multiple lines ending with period)
            while i < len(lines):
                if 'handle_stop(Connection)}.' in lines[i]:
                    i += 1
                    break
                i += 1
            # Also fix the previous clause's terminator: the line ending with };
            # before this deleted block should end with }. instead
            # Walk backwards in out to find and fix it
            for j in range(len(out) - 1, -1, -1):
                if out[j].rstrip().endswith('Rest}};'):
                    out[j] = out[j].replace('Rest}};', 'Rest}}.')
                    break
            continue

        out.append(line)
        i += 1

    with open(target, "w") as fh:
        fh.writelines(out)

    print(f"[apply_fix] Patched {target}")


if __name__ == "__main__":
    main()
