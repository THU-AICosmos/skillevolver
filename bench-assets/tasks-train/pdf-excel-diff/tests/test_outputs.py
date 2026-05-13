"""
Tests for pdf-excel-diff training variant (warehouse inventory).

Verifies that the agent correctly identifies:
1. Deleted products (present in PDF archive but not in current Excel)
2. Modified product records (different values between PDF and Excel)
"""

import json
from pathlib import Path

import pytest

REPORT_PATH = Path("/root/inventory_diff.json")
GROUND_TRUTH = Path("/tests/expected_output.json")


class TestReportFileValidity:
    """Verify the report file exists and is well-formed JSON."""

    def test_report_exists(self):
        assert REPORT_PATH.exists(), f"Report not found at {REPORT_PATH}"

    def test_report_is_json(self):
        assert REPORT_PATH.exists(), "Report does not exist"
        with open(REPORT_PATH) as fh:
            try:
                json.load(fh)
            except json.JSONDecodeError as exc:
                pytest.fail(f"Report is not valid JSON: {exc}")

    def test_report_schema(self):
        assert REPORT_PATH.exists(), "Report does not exist"
        with open(REPORT_PATH) as fh:
            payload = json.load(fh)
        assert "deleted_products" in payload, "Missing 'deleted_products' key"
        assert "modified_products" in payload, "Missing 'modified_products' key"
        assert isinstance(payload["deleted_products"], list), "'deleted_products' must be a list"
        assert isinstance(payload["modified_products"], list), "'modified_products' must be a list"


class TestDeletedProducts:
    """Check detection of removed products."""

    def _load(self):
        with open(REPORT_PATH) as fh:
            out = json.load(fh)
        with open(GROUND_TRUTH) as fh:
            exp = json.load(fh)
        return out, exp

    def test_deleted_count(self):
        out, exp = self._load()
        assert len(out["deleted_products"]) == len(exp["deleted_products"]), (
            f"Expected {len(exp['deleted_products'])} deletions, got {len(out['deleted_products'])}"
        )

    def test_deleted_codes(self):
        out, exp = self._load()
        got = set(out["deleted_products"])
        want = set(exp["deleted_products"])
        assert want - got == set(), f"Missed deleted products: {want - got}"
        assert got - want == set(), f"Wrongly marked as deleted: {got - want}"


class TestModifiedProducts:
    """Check detection of changed product fields."""

    def _load(self):
        with open(REPORT_PATH) as fh:
            out = json.load(fh)
        with open(GROUND_TRUTH) as fh:
            exp = json.load(fh)
        return out, exp

    def test_modification_count(self):
        out, exp = self._load()
        assert len(out["modified_products"]) == len(exp["modified_products"]), (
            f"Expected {len(exp['modified_products'])} modifications, got {len(out['modified_products'])}"
        )

    def test_modification_entry_fields(self):
        with open(REPORT_PATH) as fh:
            out = json.load(fh)
        for entry in out["modified_products"]:
            assert "id" in entry, "Entry missing 'id'"
            assert "field" in entry, "Entry missing 'field'"
            assert "old_value" in entry, "Entry missing 'old_value'"
            assert "new_value" in entry, "Entry missing 'new_value'"

    def test_modified_codes(self):
        out, exp = self._load()
        got_ids = {m["id"] for m in out["modified_products"]}
        want_ids = {m["id"] for m in exp["modified_products"]}
        assert want_ids - got_ids == set(), f"Missed modifications for: {want_ids - got_ids}"
        assert got_ids - want_ids == set(), f"Wrongly flagged modifications for: {got_ids - want_ids}"

    def test_modified_field_names(self):
        out, exp = self._load()
        exp_lookup = {m["id"]: m for m in exp["modified_products"]}
        out_lookup = {m["id"]: m for m in out["modified_products"]}
        for pid, want in exp_lookup.items():
            if pid in out_lookup:
                got = out_lookup[pid]
                assert got["field"] == want["field"], (
                    f"{pid}: expected field '{want['field']}', got '{got['field']}'"
                )

    def test_modified_values(self):
        out, exp = self._load()
        exp_lookup = {m["id"]: m for m in exp["modified_products"]}
        out_lookup = {m["id"]: m for m in out["modified_products"]}
        for pid, want in exp_lookup.items():
            if pid not in out_lookup:
                continue
            got = out_lookup[pid]
            # old_value
            if isinstance(want["old_value"], (int, float)) and isinstance(got["old_value"], (int, float)):
                assert abs(want["old_value"] - got["old_value"]) < 0.05, (
                    f"{pid}: old_value expected {want['old_value']}, got {got['old_value']}"
                )
            else:
                assert str(want["old_value"]) == str(got["old_value"]), (
                    f"{pid}: old_value expected '{want['old_value']}', got '{got['old_value']}'"
                )
            # new_value
            if isinstance(want["new_value"], (int, float)) and isinstance(got["new_value"], (int, float)):
                assert abs(want["new_value"] - got["new_value"]) < 0.05, (
                    f"{pid}: new_value expected {want['new_value']}, got {got['new_value']}"
                )
            else:
                assert str(want["new_value"]) == str(got["new_value"]), (
                    f"{pid}: new_value expected '{want['new_value']}', got '{got['new_value']}'"
                )


class TestEndToEnd:
    """Full comparison of output vs ground truth."""

    def test_complete_match(self):
        with open(REPORT_PATH) as fh:
            out = json.load(fh)
        with open(GROUND_TRUTH) as fh:
            exp = json.load(fh)

        assert set(out["deleted_products"]) == set(exp["deleted_products"]), "Deleted products mismatch"
        assert len(out["modified_products"]) == len(exp["modified_products"]), "Modified count mismatch"

        exp_keys = {(m["id"], m["field"]): m for m in exp["modified_products"]}
        out_keys = {(m["id"], m["field"]): m for m in out["modified_products"]}
        assert set(exp_keys.keys()) == set(out_keys.keys()), "Modified product/field combos mismatch"
