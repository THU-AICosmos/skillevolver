"""
Test for software-dependency-audit task (Python requirements.txt variant).

Verifies the agent generated a proper security audit CSV file
containing HIGH and CRITICAL vulnerabilities from the requirements.txt file.
"""

import os
import csv
import io
import pytest


class TestSecurityAuditTask:
    """Test suite for the software dependency audit task."""

    # Expected CSV content for exact match validation
    EXPECTED_CSV_CONTENT = """Package,Version,CVE_ID,Severity,CVSS_Score,Fixed_Version,Title,Url
cryptography,41.0.3,CVE-2023-50782,HIGH,7.5,42.0.0,python-cryptography: Bleichenbacher timing oracle attack against RSA decryption - incomplete fix for CVE-2020-25659,https://avd.aquasec.com/nvd/cve-2023-50782
cryptography,41.0.3,CVE-2024-26130,HIGH,7.5,42.0.4,python-cryptography: NULL pointer dereference with pkcs12.serialize_key_and_certificates when called with a non-matching certificate and private key and an hmac_hash override,https://avd.aquasec.com/nvd/cve-2024-26130
pillow,10.0.0,CVE-2023-50447,CRITICAL,8.1,10.2.0,pillow: Arbitrary Code Execution via the environment parameter,https://avd.aquasec.com/nvd/cve-2023-50447
pillow,10.0.0,CVE-2023-4863,HIGH,8.8,10.0.1,libwebp: Heap buffer overflow in WebP Codec,https://avd.aquasec.com/nvd/cve-2023-4863
pillow,10.0.0,CVE-2024-28219,HIGH,5.9,10.3.0,python-pillow: buffer overflow in _imagingcms.c,https://avd.aquasec.com/nvd/cve-2024-28219
urllib3,2.6.0,CVE-2026-21441,HIGH,7.5,2.6.3,urllib3: urllib3 vulnerable to decompression-bomb safeguard bypass when following HTTP redirects (streaming API),https://avd.aquasec.com/nvd/cve-2026-21441
werkzeug,2.3.6,CVE-2024-34069,HIGH,7.5,3.0.3,python-werkzeug: user may execute code on a developer's machine,https://avd.aquasec.com/nvd/cve-2024-34069"""

    EXPECTED_HEADERS = ["Package", "Version", "CVE_ID", "Severity", "CVSS_Score", "Fixed_Version", "Title", "Url"]
    ALLOWED_SEVERITIES = ["HIGH", "CRITICAL"]
    VALID_CVE_PREFIXES = ["CVE-", "GHSA-", "PYSEC-"]

    def get_csv_path(self):
        """Find the security audit CSV file in expected locations, raising error if not found."""
        paths = ["/root/security_audit.csv", "security_audit.csv"]
        for path in paths:
            if os.path.exists(path):
                return path
        raise FileNotFoundError(
            f"Security audit CSV file not found. Expected one of: {', '.join(paths)}"
        )

    def test_csv_structure_and_content(self):
        """Verify CSV exists, is parseable, and has correct headers."""
        # File existence - will raise FileNotFoundError if not found
        path = self.get_csv_path()

        # CSV is parseable and has correct headers
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                rows = list(reader)
        except csv.Error as e:
            pytest.fail(f"CSV file is not properly formatted: {e}")

        assert headers == self.EXPECTED_HEADERS, \
            f"CSV headers mismatch. Expected {self.EXPECTED_HEADERS}, got {headers}"

        print(f"Successfully parsed {len(rows)} vulnerability records")

    @pytest.mark.parametrize("field_name", ["Package", "Version", "CVE_ID", "Severity"])
    def test_required_fields_non_empty(self, field_name):
        """Verify each row has non-empty required fields."""
        path = self.get_csv_path()

        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            print(f"Note: No vulnerabilities to validate for field '{field_name}'")
            return

        for i, row in enumerate(rows):
            field_value = row.get(field_name, '').strip()
            assert field_value, \
                f"Row {i+1}: Required field '{field_name}' is empty or missing"

    def test_vulnerability_severity_and_format(self):
        """Verify all vulnerabilities have valid severity and CVE ID format."""
        path = self.get_csv_path()

        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            print("Note: No HIGH or CRITICAL vulnerabilities found")
            return

        for i, row in enumerate(rows):
            # Verify severity
            severity = row.get('Severity', '').strip()
            assert severity in self.ALLOWED_SEVERITIES, \
                f"Row {i+1}: Invalid severity '{severity}'. Only {self.ALLOWED_SEVERITIES} are allowed."

            # Verify CVE ID format
            cve_id = row.get('CVE_ID', '').strip()
            has_valid_prefix = any(cve_id.startswith(prefix) for prefix in self.VALID_CVE_PREFIXES)
            assert has_valid_prefix or len(cve_id) > 0, \
                f"Row {i+1}: CVE_ID '{cve_id}' should start with one of {self.VALID_CVE_PREFIXES} or be a valid identifier"

    def _csv_to_dict(self, csv_content):
        """Convert CSV content to a dict keyed by (Package, CVE_ID) for comparison."""
        reader = csv.DictReader(io.StringIO(csv_content.strip()))
        result = {}
        for row in reader:
            # Normalize row data
            item = {k: v.strip() for k, v in row.items()}

            # Normalize Fixed_Version: treat empty string as "N/A" to match expected consistency
            if not item.get("Fixed_Version"):
                item["Fixed_Version"] = "N/A"

            result[(row['Package'], row['CVE_ID'])] = item
        return result

    def test_csv_matches_ground_truth(self):
        """Verify generated CSV contains the same vulnerability records as expected (order independent)."""
        generated_path = self.get_csv_path()

        # Read generated CSV and convert to dict
        with open(generated_path, 'r', encoding='utf-8') as f:
            generated_dict = self._csv_to_dict(f.read())

        # Convert expected CSV to dict
        expected_dict = self._csv_to_dict(self.EXPECTED_CSV_CONTENT)

        # Direct dict comparison (order independent)
        assert generated_dict == expected_dict, \
            "Generated CSV content does not match expected vulnerabilities"
