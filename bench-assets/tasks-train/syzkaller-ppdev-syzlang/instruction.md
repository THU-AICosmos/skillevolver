Write syzkaller syzlang support for the Linux hardware watchdog timer driver. Right now /dev/watchdog* isn't described.

Create:
- /opt/syzkaller/sys/linux/dev_watchdog.txt
- /opt/syzkaller/sys/linux/dev_watchdog.txt.const

In dev_watchdog.txt (syzlang descriptions), add:
- include <linux/watchdog.h>
- resource fd_watchdog[fd]
- an opener for /dev/watchdog# (syz_open_dev) that returns fd_watchdog
- a write specialization for the watchdog (write$watchdog) to send keep-alive or magic close bytes
- ioctl descriptions for all watchdog ioctls from linux/watchdog.h (11 total), with correct in/out/inout arg directions
- watchdog_info struct { options, firmware_version, identity }
- WDIOF capability flags and WDIOS option flags

In dev_watchdog.txt.const (the constant values file):
- arches = amd64, 386
- the ioctl numbers and flag values used by your .txt

Run these commands to verify your descriptions:
```bash
cd /opt/syzkaller
make descriptions
make all TARGETOS=linux TARGETARCH=amd64
```
