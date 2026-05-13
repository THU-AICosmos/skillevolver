"""
Tests for the watchdog syzlang description task.
Tests verify:
1. Files exist and compile
2. Correct resource and device opening
3. Key ioctls are defined with correct signatures
4. Structs and flags are properly defined
5. Constants have correct values
6. Full syzkaller build succeeds
"""

import os
import re
import subprocess

SYZLANG_FILE = "/opt/syzkaller/sys/linux/dev_watchdog.txt"
CONST_FILE = "/opt/syzkaller/sys/linux/dev_watchdog.txt.const"


def read_syzlang_file():
    """Read the generated syzlang file."""
    assert os.path.exists(SYZLANG_FILE), f"syzlang file not found at {SYZLANG_FILE}"
    with open(SYZLANG_FILE) as f:
        return f.read()


def read_const_file():
    """Read the constants file."""
    assert os.path.exists(CONST_FILE), f"const file not found at {CONST_FILE}"
    with open(CONST_FILE) as f:
        return f.read()


def parse_const_file():
    """Parse the constants file into a dictionary."""
    content = read_const_file()
    consts = {}
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("arches"):
            continue
        if "=" in line:
            parts = line.split("=", 1)
            name = parts[0].strip()
            value_part = parts[1].split(",")[0].strip()
            try:
                consts[name] = int(value_part)
            except ValueError:
                pass
    return consts


class TestFilesAndIncludes:
    """Test that required files exist with proper includes."""

    def test_files_exist_and_have_includes(self):
        """Check that both files exist and syzlang has required includes."""
        assert os.path.exists(SYZLANG_FILE), f"File {SYZLANG_FILE} does not exist"
        assert os.path.exists(CONST_FILE), f"File {CONST_FILE} does not exist"

        content = read_syzlang_file()
        assert re.search(r"include\s*<.*watchdog\.h>", content), "Missing include for watchdog.h"


class TestCompilation:
    """Test that descriptions compile successfully."""

    def test_compilation_and_const_validation(self):
        """Check make descriptions succeeds and const file is valid."""
        result = subprocess.run(["make", "descriptions"], cwd="/opt/syzkaller", capture_output=True, text=True, timeout=300)
        assert result.returncode == 0, f"make descriptions failed:\n{result.stderr}\n{result.stdout}"

        result = subprocess.run(["make", "generate"], cwd="/opt/syzkaller", capture_output=True, text=True, timeout=300)
        combined = result.stdout + result.stderr
        assert "dev_watchdog.txt" not in combined.lower() or result.returncode == 0, f"syz-sysgen reported errors for watchdog:\n{combined}"

        content = read_const_file()
        lines = [line.strip() for line in content.split("\n") if line.strip() and not line.startswith("#")]
        has_arch = any("arches" in line for line in lines)
        assert has_arch, "Const file missing 'arches' declaration"
        const_lines = [line for line in lines if "=" in line and "arches" not in line]
        assert len(const_lines) >= 10, f"Const file has too few constants ({len(const_lines)}), expected 10+"


class TestResourceAndOpen:
    """Test resource definition and device opening."""

    def test_fd_watchdog_resource_and_open(self):
        """Check fd_watchdog resource and syz_open_dev are correctly defined."""
        content = read_syzlang_file()
        assert re.search(r"resource\s+fd_watchdog\s*\[\s*fd\s*\]", content), "Missing resource fd_watchdog[fd] definition"
        assert re.search(r'syz_open_dev\$\w*watchdog.*"/dev/watchdog#"', content), "Missing syz_open_dev with /dev/watchdog# pattern"
        assert re.search(r"syz_open_dev\$\w*watchdog[^)]+\)\s+fd_watchdog", content), "syz_open_dev should return fd_watchdog resource type"


class TestCoreIoctls:
    """Test that core ioctls are defined with correct signatures."""

    def test_all_ioctls_with_correct_signatures(self):
        """Check all watchdog ioctls are defined with correct signatures."""
        content = read_syzlang_file()

        # Check SETTIMEOUT and SETPRETIMEOUT have inout direction (_IOWR ioctls)
        assert re.search(r"ioctl\$WDIOC_SETTIMEOUT\s*\([^)]*ptr\s*\[\s*inout\s*,", content), \
            "ioctl$WDIOC_SETTIMEOUT should have ptr[inout, ...] argument (it is _IOWR)"
        assert re.search(r"ioctl\$WDIOC_SETPRETIMEOUT\s*\([^)]*ptr\s*\[\s*inout\s*,", content), \
            "ioctl$WDIOC_SETPRETIMEOUT should have ptr[inout, ...] argument (it is _IOWR)"

        # Check getter ioctls have out direction
        assert re.search(r"ioctl\$WDIOC_GETTIMEOUT\s*\([^)]*ptr\s*\[\s*out\s*,", content), \
            "ioctl$WDIOC_GETTIMEOUT should have ptr[out, ...] argument"
        assert re.search(r"ioctl\$WDIOC_GETSUPPORT\s*\([^)]*ptr\s*\[\s*out\s*,", content), \
            "ioctl$WDIOC_GETSUPPORT should have ptr[out, ...] argument"

        # Check all required ioctls are present
        required_ioctls = [
            "WDIOC_GETSUPPORT",
            "WDIOC_GETSTATUS",
            "WDIOC_GETBOOTSTATUS",
            "WDIOC_GETTEMP",
            "WDIOC_SETOPTIONS",
            "WDIOC_KEEPALIVE",
            "WDIOC_SETTIMEOUT",
            "WDIOC_GETTIMEOUT",
            "WDIOC_SETPRETIMEOUT",
            "WDIOC_GETPRETIMEOUT",
            "WDIOC_GETTIMELEFT",
        ]
        missing = [ioctl for ioctl in required_ioctls if not re.search(rf"ioctl\${ioctl}\b", content)]
        assert not missing, f"Missing ioctls: {missing}"


class TestStructsAndFlags:
    """Test struct and flag definitions."""

    def test_structs_and_flags_defined(self):
        """Check watchdog_info struct and WDIOF/WDIOS flags are defined."""
        content = read_syzlang_file()

        # Check watchdog_info struct
        struct_match = re.search(r"watchdog_info\s*\{([^}]+)\}", content)
        assert struct_match, "Missing watchdog_info struct definition"
        struct_body = struct_match.group(1)
        assert "options" in struct_body, "watchdog_info missing 'options' field"
        assert "firmware_version" in struct_body, "watchdog_info missing 'firmware_version' field"
        assert "identity" in struct_body, "watchdog_info missing 'identity' field"

        # Check WDIOF capability flags
        assert re.search(r"WDIOF_OVERHEAT", content), "Missing WDIOF_OVERHEAT"
        assert re.search(r"WDIOF_SETTIMEOUT", content), "Missing WDIOF_SETTIMEOUT"
        assert re.search(r"WDIOF_MAGICCLOSE", content), "Missing WDIOF_MAGICCLOSE"
        assert re.search(r"WDIOF_KEEPALIVEPING", content), "Missing WDIOF_KEEPALIVEPING"

        # Check WDIOS option flags
        assert re.search(r"WDIOS_DISABLECARD", content), "Missing WDIOS_DISABLECARD"
        assert re.search(r"WDIOS_ENABLECARD", content), "Missing WDIOS_ENABLECARD"
        assert re.search(r"WDIOS_TEMPPANIC", content), "Missing WDIOS_TEMPPANIC"


class TestConstantValues:
    """Test that constants have correct values."""

    def test_ioctl_and_flag_constant_values(self):
        """Check ioctl and flag constants have correct values."""
        consts = parse_const_file()

        # WDIOC_GETSUPPORT: _IOR('W', 0, struct watchdog_info) where sizeof=40
        # = 0x80000000 | (40 << 16) | (0x57 << 8) | 0 = 0x80285700 = 2150127360
        assert consts.get("WDIOC_GETSUPPORT") == 2150127360, "WDIOC_GETSUPPORT should be 2150127360"

        # WDIOC_GETSTATUS: _IOR('W', 1, int) = 0x80045701 = 2147768065
        assert consts.get("WDIOC_GETSTATUS") == 2147768065, "WDIOC_GETSTATUS should be 2147768065"

        # WDIOC_SETTIMEOUT: _IOWR('W', 6, int) = 0xC0045706 = 3221509894
        assert consts.get("WDIOC_SETTIMEOUT") == 3221509894, "WDIOC_SETTIMEOUT should be 3221509894"

        # WDIOF capability flags
        assert consts.get("WDIOF_OVERHEAT") == 1, "WDIOF_OVERHEAT should be 1"
        assert consts.get("WDIOF_SETTIMEOUT") == 128, "WDIOF_SETTIMEOUT should be 128"
        assert consts.get("WDIOF_KEEPALIVEPING") == 32768, "WDIOF_KEEPALIVEPING should be 32768"

        # WDIOS option flags
        assert consts.get("WDIOS_DISABLECARD") == 1, "WDIOS_DISABLECARD should be 1"
        assert consts.get("WDIOS_ENABLECARD") == 2, "WDIOS_ENABLECARD should be 2"


class TestSyzkallerBuild:
    """Test that syzkaller builds successfully."""

    def test_build_syzkaller(self):
        """Build syzkaller binaries to verify descriptions are valid."""
        result = subprocess.run(
            ["make", "all"],
            cwd="/opt/syzkaller",
            capture_output=True,
            text=True,
            timeout=600,
            env={**os.environ, "TARGETOS": "linux", "TARGETARCH": "amd64"},
        )
        assert result.returncode == 0, f"make all failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
