#!/bin/bash
set -e

# Oracle solution for watchdog syzlang descriptions
# Generates syzlang description and const files for the Linux watchdog timer driver

cd /opt/syzkaller/sys/linux

# Use Python to compute ioctl encodings and generate both files
python3 << 'PYEOF'
import os

# Linux ioctl number encoding helpers
def ioctl_io(type_ch, nr):
    """_IO: no data transfer"""
    return (ord(type_ch) << 8) | nr

def ioctl_ior(type_ch, nr, sz):
    """_IOR: kernel writes to userspace"""
    return 0x80000000 | (sz << 16) | (ord(type_ch) << 8) | nr

def ioctl_iow(type_ch, nr, sz):
    """_IOW: userspace writes to kernel"""
    return 0x40000000 | (sz << 16) | (ord(type_ch) << 8) | nr

def ioctl_iowr(type_ch, nr, sz):
    """_IOWR: bidirectional"""
    return 0xC0000000 | (sz << 16) | (ord(type_ch) << 8) | nr

# Watchdog ioctl table from linux/watchdog.h
# WATCHDOG_IOCTL_BASE = 'W' = 0x57
# struct watchdog_info is 40 bytes (uint32 options + uint32 firmware_version + char identity[32])
WDT_IOCTL_TABLE = [
    # (name, encoder, nr, size, syzlang_direction, syzlang_type)
    ("WDIOC_GETSUPPORT",    "ior",  0, 40, "out",   "watchdog_info"),
    ("WDIOC_GETSTATUS",     "ior",  1,  4, "out",   "int32"),
    ("WDIOC_GETBOOTSTATUS", "ior",  2,  4, "out",   "int32"),
    ("WDIOC_GETTEMP",       "ior",  3,  4, "out",   "int32"),
    ("WDIOC_SETOPTIONS",    "ior",  4,  4, "in",    "flags[wdios_options, int32]"),
    ("WDIOC_KEEPALIVE",     "ior",  5,  4, "out",   "int32"),
    ("WDIOC_SETTIMEOUT",    "iowr", 6,  4, "inout", "int32"),
    ("WDIOC_GETTIMEOUT",    "ior",  7,  4, "out",   "int32"),
    ("WDIOC_SETPRETIMEOUT", "iowr", 8,  4, "inout", "int32"),
    ("WDIOC_GETPRETIMEOUT", "ior",  9,  4, "out",   "int32"),
    ("WDIOC_GETTIMELEFT",   "ior", 10,  4, "out",   "int32"),
]

# WDIOF capability flags from linux/watchdog.h
WDIOF_CAPABILITY_FLAGS = {
    "WDIOF_OVERHEAT":      0x0001,
    "WDIOF_FANFAULT":      0x0002,
    "WDIOF_EXTERN1":       0x0004,
    "WDIOF_EXTERN2":       0x0008,
    "WDIOF_POWERUNDER":    0x0010,
    "WDIOF_CARDRESET":     0x0020,
    "WDIOF_POWEROVER":     0x0040,
    "WDIOF_SETTIMEOUT":    0x0080,
    "WDIOF_MAGICCLOSE":    0x0100,
    "WDIOF_PRETIMEOUT":    0x0200,
    "WDIOF_ALARMONLY":     0x0400,
    "WDIOF_KEEPALIVEPING": 0x8000,
}

# WDIOS set-options flags
WDIOS_OPTION_FLAGS = {
    "WDIOS_DISABLECARD": 0x0001,
    "WDIOS_ENABLECARD":  0x0002,
    "WDIOS_TEMPPANIC":   0x0004,
}

ENCODERS = {
    "io":   ioctl_io,
    "ior":  ioctl_ior,
    "iow":  ioctl_iow,
    "iowr": ioctl_iowr,
}

def compute_val(enc_name, nr, sz):
    return ENCODERS[enc_name]('W', nr, sz)

# ---- Build syzlang description ----
desc = []
desc.append("# Syzkaller descriptions for Linux watchdog timer driver")
desc.append("# Device: /dev/watchdog*")
desc.append("# Header: linux/watchdog.h")
desc.append("")
desc.append("include <linux/watchdog.h>")
desc.append("")
desc.append("resource fd_watchdog[fd]")
desc.append("")
desc.append('syz_open_dev$watchdog(dev ptr[in, string["/dev/watchdog#"]], id intptr, flags flags[open_flags]) fd_watchdog')
desc.append("")
desc.append("# Write to watchdog (keepalive byte or magic close character)")
desc.append('write$watchdog(fd fd_watchdog, buf ptr[in, array[int8]], count len[buf])')
desc.append("")

# Ioctl entries
for name, enc, nr, sz, direction, typ in WDT_IOCTL_TABLE:
    desc.append(f"ioctl${name}(fd fd_watchdog, cmd const[{name}], arg ptr[{direction}, {typ}])")

desc.append("")
desc.append("# watchdog_info struct (from linux/watchdog.h)")
desc.append("watchdog_info {")
desc.append("\toptions\t\t\tflags[wdiof_capability_flags, int32]")
desc.append("\tfirmware_version\tint32")
desc.append("\tidentity\t\tarray[int8, 32]")
desc.append("}")
desc.append("")
desc.append("# WDIOF capability flags (watchdog features)")
desc.append("wdiof_capability_flags = " + ", ".join(WDIOF_CAPABILITY_FLAGS.keys()))
desc.append("")
desc.append("# WDIOS set-options flags")
desc.append("wdios_options = " + ", ".join(WDIOS_OPTION_FLAGS.keys()))

with open("dev_watchdog.txt", "w") as fh:
    fh.write("\n".join(desc) + "\n")
print("Wrote dev_watchdog.txt")

# ---- Build constants file ----
clines = []
clines.append("# Constants for watchdog syzlang descriptions")
clines.append("# Computed from linux/watchdog.h ioctl macros (WATCHDOG_IOCTL_BASE = 'W')")
clines.append("arches = amd64, 386")
clines.append("")
clines.append("# Ioctl number constants")

for name, enc, nr, sz, _, _ in sorted(WDT_IOCTL_TABLE, key=lambda r: r[0]):
    val = compute_val(enc, nr, sz)
    clines.append(f"{name} = {val}")

clines.append("")
clines.append("# WDIOF capability flags")
for flag_name, flag_val in sorted(WDIOF_CAPABILITY_FLAGS.items()):
    clines.append(f"{flag_name} = {flag_val}")

clines.append("")
clines.append("# WDIOS option flags")
for flag_name, flag_val in sorted(WDIOS_OPTION_FLAGS.items()):
    clines.append(f"{flag_name} = {flag_val}")

with open("dev_watchdog.txt.const", "w") as fh:
    fh.write("\n".join(clines) + "\n")
print("Wrote dev_watchdog.txt.const")
PYEOF

cd /opt/syzkaller

# Compile descriptions
echo "=== Running make descriptions ==="
make descriptions

# Full build
echo "=== Running make all ==="
make all TARGETOS=linux TARGETARCH=amd64

echo "=== Watchdog solution complete ==="
