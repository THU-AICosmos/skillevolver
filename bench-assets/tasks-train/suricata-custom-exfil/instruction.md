You're investigating suspected command-and-control (C2) beaconing hidden inside health-check API traffic.

You need to write Suricata signature(s) that alert on the C2 beacon pattern, and avoid false positives.

The C2 beacon pattern should alert only when all of the following are true:(1)HTTP `PUT` request
(2)Request path is exactly /api/v3/heartbeat (3)Request header contains `X-Beacon-Type: command`
(4)Body has data= with a hex-encoded value ≥ 100 chars (only 0-9a-fA-F), and (5)Body has `checksum=` with exactly 40 hex chars

You'll get pcaps in /root/pcaps/, config at /root/suricata.yaml, and a rules file at /root/local.rules

You need to update `/root/local.rules` so that Suricata raises an alert with `sid:1000001` for true C2 beacon traffic.
