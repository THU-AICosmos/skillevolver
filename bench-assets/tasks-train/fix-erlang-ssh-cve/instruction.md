Your team has received an urgent security incident report: an attacker was able to gain remote shell access to a production Erlang/OTP node running an SSH daemon, without ever providing valid credentials. The intrusion logs show that the attacker sent crafted SSH protocol messages that bypassed the authentication phase entirely, allowing arbitrary Erlang term evaluation and OS command execution on the server.

The vulnerable Erlang/OTP source tree is located at `/app/workspace/otp_src_27.3.2`. Your objective is to:

1. Identify which part of the SSH connection handling code fails to verify that the user has been authenticated before processing connection-layer protocol messages.
2. Apply a targeted code fix so that the SSH daemon rejects any connection-layer message (message type 80 and above per RFC 4252 Section 6) that arrives before the client has successfully authenticated, responding with a protocol-level disconnect.

After your fix, the daemon must continue to allow legitimate password-authenticated SSH sessions and authorized command execution, while blocking any unauthenticated connection-layer messages from being processed.

Only modify files within the provided source tree. You do not need to compile or restart the server.
