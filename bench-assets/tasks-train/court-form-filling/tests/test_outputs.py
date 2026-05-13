"""
Tests for court-form-filling task (SC-120 Defendant's Claim form).

Verifies that the agent correctly fills out the SC-120 "Defendant's Claim
and ORDER to Go to Small Claims Court" form based on the provided case
description (Marcus Rivera vs. Thornwood Auto Repair LLC).

Uses pdftotext to extract visible text content from the PDF, which works
reliably for both AcroForms and XFA forms regardless of the filling method used.
For checkboxes, extracts values from XFA XML stream or AcroForm fields.
"""

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

OUTPUT_FILE = Path("/root/sc120-filled.pdf")
INPUT_FILE = Path("/root/sc120-blank.pdf")


def extract_xfa_xml(pdf_path: Path) -> str:
    """
    Extract XFA XML datasets from a PDF file.
    Returns the raw XML string or empty string if not found.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))

        # Try to access XFA data
        if "/AcroForm" in reader.trailer["/Root"]:
            acroform = reader.trailer["/Root"]["/AcroForm"]
            if "/XFA" in acroform:
                xfa = acroform["/XFA"]
                # XFA can be an array of [name, stream, name, stream, ...]
                if isinstance(xfa, list):
                    for i in range(0, len(xfa), 2):
                        if i + 1 < len(xfa):
                            stream_name = str(xfa[i])
                            if stream_name == "datasets":
                                stream_obj = xfa[i + 1].get_object()
                                return stream_obj.get_data().decode("utf-8", errors="ignore")
    except Exception:
        pass
    return ""


def extract_checkbox_values(pdf_path: Path) -> dict:
    """
    Extract checkbox/radio button values from a PDF.
    Tries multiple methods: XFA XML parsing, then AcroForm fields.

    Returns dict mapping field name patterns to their values.
    Values are normalized to: "1" (first option), "2" (second option), etc.
    """
    checkbox_values = {}

    # Method 1: Extract from XFA XML
    xfa_xml = extract_xfa_xml(pdf_path)
    if xfa_xml:
        checkbox_values.update(parse_xfa_checkboxes(xfa_xml))

    # Method 2: Try pypdf get_fields() for AcroForms
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        fields = reader.get_fields() or {}

        for name, field in fields.items():
            # Check if it's a checkbox/radio field
            if "Checkbox" in name or "CheckBox" in name or field.get("/FT") in ["/Btn"]:
                value = field.get("/V", "")
                if value:
                    if hasattr(value, "get_object"):
                        value = str(value.get_object())
                    else:
                        value = str(value)
                    # Normalize value
                    value = value.strip("/")
                    if value and value not in ["Off", "None", ""]:
                        checkbox_values[name] = value
    except Exception:
        pass

    return checkbox_values


def parse_xfa_checkboxes(xfa_xml: str) -> dict:
    """
    Parse XFA XML to extract checkbox values.
    XFA stores checkbox states in the datasets XML.
    """
    checkbox_values = {}

    try:
        # Clean XML namespaces for easier parsing
        clean_xml = re.sub(r'\sxmlns[^"]*"[^"]*"', '', xfa_xml)
        clean_xml = re.sub(r'<([a-zA-Z0-9_]+):', r'<', clean_xml)
        clean_xml = re.sub(r'</([a-zA-Z0-9_]+):', r'</', clean_xml)

        root = ET.fromstring(clean_xml)

        # Find all elements that look like checkbox fields
        def find_checkboxes(element, path=""):
            tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
            current_path = f"{path}.{tag}" if path else tag

            # Check if this looks like a checkbox field
            if "Checkbox" in tag or "checkbox" in tag.lower() or tag.startswith("Ch") or "CheckBox" in tag:
                if element.text and element.text.strip():
                    checkbox_values[current_path] = element.text.strip()

            # Also capture any field with value 1, 2, Yes, No, On, Off
            if element.text and element.text.strip() in ["1", "2", "Yes", "No", "On", "Off"]:
                checkbox_values[current_path] = element.text.strip()

            for child in element:
                find_checkboxes(child, current_path)

        find_checkboxes(root)
    except Exception:
        pass

    return checkbox_values


def checkbox_is_checked(value: str) -> bool:
    """Check if a checkbox value indicates it's checked."""
    if not value:
        return False
    v = str(value).lower().strip("/")
    return v in ["1", "yes", "on", "true", "checked"]


def checkbox_value_matches(actual: str, expected: str) -> bool:
    """
    Check if checkbox value matches expected.
    Expected format: "/1" for first option, "/2" for second option.
    """
    if not actual:
        return False

    # Normalize both values
    actual_norm = str(actual).strip("/").lower()
    expected_norm = str(expected).strip("/").lower()

    # Direct match
    if actual_norm == expected_norm:
        return True

    # Handle common equivalents
    equivalents = {
        "1": ["yes", "on", "true", "checked"],
        "2": ["no", "off", "false", "unchecked"],
    }

    for canonical, aliases in equivalents.items():
        if expected_norm == canonical or expected_norm in aliases:
            if actual_norm == canonical or actual_norm in aliases:
                return True

    return False


def extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract all visible text from a PDF using pdftotext.
    This works for both AcroForms and XFA forms.
    """
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        pytest.fail(f"pdftotext failed: {e}")
    return ""


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, collapse whitespace."""
    return " ".join(text.lower().split())


# Text values that must appear in the filled PDF
# Format: (expected_text, description)
REQUIRED_TEXT_VALUES = [
    # Plaintiff (the party being sued back on SC-120)
    ("Thornwood Auto Repair LLC", "plaintiff_name"),
    ("2210 International Blvd", "plaintiff_address"),
    ("94606", "plaintiff_zip"),
    ("5105557432", "plaintiff_phone"),

    # Defendant (the filer on SC-120)
    ("Marcus Rivera", "defendant_name"),
    ("1428 Linden St", "defendant_address"),
    ("Oakland", "defendant_city"),  # Will appear multiple times (both parties)
    ("94607", "defendant_zip"),
    ("5103340912", "defendant_phone"),

    # Claim information - check for amount in various formats
    ("3275", "claim_amount"),  # May appear as 3275, $3,275, etc.
    ("transmission", "claim_reason_keyword"),

    # Dates for incident start/end
    ("2025-11-12", "incident_start_date"),
    ("2026-02-04", "incident_end_date"),

    # Claim calculation should mention the towing / corrective repair
    ("corrective", "claim_calculation_keyword"),
]

# Checkbox fields that must be checked correctly
# Format: (field_name_pattern, description, expected_value, should_be_checked)
# - field_name_pattern: substring to match in the field name
# - expected_value: "/1" = first option (Yes), "/2" = second option (No)
# - should_be_checked: True if this specific option should be selected
#
# SC-120 uses separate fields for Yes vs No (Ch1[0] vs Ch1[1], etc.).
# We assert on the specific option that should be selected.
REQUIRED_CHECKBOXES = [
    # Question 4: Have you asked the Plaintiff to pay? -> Yes (Ch1[0])
    ("item4[0].Ch1[0]", "asked_to_pay_yes", "/1", True),

    # Question 5: Attorney-client fee dispute? -> No (Ch2[1])
    ("item5[0].Ch2[1]", "attorney_fee_dispute_no", "/2", True),

    # Question 6: Suing a public entity? -> No (Ch3[1])
    ("item6[0].Ch3[1]", "suing_public_entity_no", "/2", True),

    # Question 7: Filed more than 12 small claims in the last 12 months? -> No (Ch4[1])
    ("item7[0].Ch4[1]", "filed_12_claims_no", "/2", True),
]

# Checkbox fields that must NOT be checked (should be Off/unchecked)
# Format: (field_name_pattern, description)
UNCHECKED_CHECKBOXES = [
    # Q4 sibling -- "No" option must be left off (we answered Yes)
    ("item4[0].Ch1[1]", "asked_to_pay_no_sibling_unchecked"),
    # Q5 sibling -- "Yes" option must be left off (we answered No)
    ("item5[0].Ch2[0]", "attorney_fee_yes_sibling_unchecked"),
    # Q5 arbitration sub-checkbox (only relevant if Yes)
    ("CheckBox09", "arbitration_checkbox_unchecked"),
    # Q6 sibling -- "Yes" option must be left off
    ("item6[0].Ch3[0]", "public_entity_yes_sibling_unchecked"),
    # Q6 "claim filed with entity" sub-checkbox
    ("CheckBox11", "public_entity_claim_filed_unchecked"),
    # Q7 sibling -- "Yes" option must be left off
    ("item7[0].Ch4[0]", "filed_12_claims_yes_sibling_unchecked"),
    # Item 3 "need more space" checkbox
    ("List3[0].CheckBox05", "need_more_space_unchecked"),
    # Header "more than 2 plaintiffs / defendants / fictitious name" checkboxes
    ("item1[0].CheckBox01", "more_than_2_plaintiffs_unchecked"),
    ("item1[0].CheckBox02", "plaintiff_military_duty_unchecked"),
    ("item2[0].CheckBox03", "more_than_2_defendants_unchecked"),
    ("item2[0].CheckBox04", "defendant_fictitious_name_unchecked"),
]

# Fields that should be empty (court fills in, or second plaintiff/defendant)
# Format: (field_name, description)
EMPTY_FIELDS = [
    # Page 1 clerk-filled trial-schedule block
    ("SC-120[0].Page1[0].CourtInfo[0].CourtInfo_ft[0]", "page1_court_info"),
    ("SC-120[0].Page1[0].CourtInfo[0].CaseNumber_ft[0]", "page1_case_number"),
    ("SC-120[0].Page1[0].CourtInfo[0].CaseName_ft[0]", "page1_case_name"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText02[0]", "page1_trial_02"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText03[0]", "page1_trial_03"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText04[0]", "page1_trial_04"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText05[0]", "page1_trial_05"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText06[0]", "page1_trial_06"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText07[0]", "page1_trial_07"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText08[0]", "page1_trial_08"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText09[0]", "page1_trial_09"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText10[0]", "page1_trial_10"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText11[0]", "page1_trial_11"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText12[0]", "page1_trial_12"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText13[0]", "page1_trial_13"),
    ("SC-120[0].Page1[0].Order[0].Trial[0].FillText16[0]", "page1_trial_16"),
    # Second plaintiff / second defendant (we only have one of each)
    ("SC-120[0].Page2[0].List1[0].item1[0].Plaintiff2Name[0]", "second_plaintiff_name"),
    ("SC-120[0].Page2[0].List2[0].item2[0].Def2Name[0]", "second_defendant_name"),
    # Military-duty plaintiff name (none on active military duty)
    ("SC-120[0].Page2[0].List1[0].item1[0].PlaintiffMilName[0]", "plaintiff_military_name"),
    # Q6: public-entity claim-filed date (not suing a public entity)
    ("SC-120[0].Page3[0].List6[0].item6[0].FillText71[0]", "public_entity_claim_date"),
    # Second signature block (only one defendant signs)
    ("SC-120[0].Page3[0].List10[0].Li1[0].Field2[0]", "second_defendant_sign_name"),
]


@pytest.fixture(scope="module")
def pdf_text():
    """Extract text content from the filled PDF using pdftotext."""
    if not OUTPUT_FILE.exists():
        pytest.fail(f"Output file not found at {OUTPUT_FILE}")

    text = extract_pdf_text(OUTPUT_FILE)
    if not text:
        pytest.fail("Failed to extract text from PDF")

    print(f"\n[PDF Text Extraction] Extracted {len(text)} characters")
    return text


@pytest.fixture(scope="module")
def blank_pdf_text():
    """Extract text content from the blank PDF for comparison."""
    if not INPUT_FILE.exists():
        return ""
    return extract_pdf_text(INPUT_FILE)


@pytest.fixture(scope="module")
def checkbox_data():
    """Extract checkbox values from the filled PDF."""
    if not OUTPUT_FILE.exists():
        pytest.fail(f"Output file not found at {OUTPUT_FILE}")

    values = extract_checkbox_values(OUTPUT_FILE)
    print(f"\n[Checkbox Extraction] Found {len(values)} checkbox values")
    if values:
        for name, val in sorted(values.items()):
            if "Checkbox" in name or "CheckBox" in name or ".Ch" in name:
                print(f"  {name}: {val}")
    return values


@pytest.fixture(scope="module")
def pdf_field_values():
    """Extract all field values from the filled PDF using pypdf."""
    from pypdf import PdfReader

    if not OUTPUT_FILE.exists():
        pytest.fail(f"Output file not found at {OUTPUT_FILE}")

    reader = PdfReader(str(OUTPUT_FILE))
    fields = reader.get_fields() or {}

    field_values = {}
    for name, field in fields.items():
        value = field.get("/V", "")
        if value:
            if hasattr(value, "get_object"):
                try:
                    value = str(value.get_object())
                except:
                    value = str(value)
            else:
                value = str(value)
        field_values[name] = value if value else ""

    return field_values


class TestPDFValid:
    """Test that the output file exists and is valid."""

    def test_output_file_valid(self, pdf_text):
        """Verify PDF exists, is valid, not empty, modified from input, and text extractable."""
        assert OUTPUT_FILE.exists(), f"Output file not found at {OUTPUT_FILE}"

        with open(OUTPUT_FILE, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-", "Output file is not a valid PDF"

        size = OUTPUT_FILE.stat().st_size
        assert size > 1000, f"Output file seems too small ({size} bytes)"

        input_size = INPUT_FILE.stat().st_size
        output_size = OUTPUT_FILE.stat().st_size
        if input_size == output_size:
            with open(INPUT_FILE, "rb") as f1, open(OUTPUT_FILE, "rb") as f2:
                assert f1.read() != f2.read(), "Output appears identical to input"

        # Verify text extraction worked
        assert len(pdf_text) > 100, "PDF text content is too short"


class TestRequiredContent:
    """Test that all required content appears in the filled PDF."""

    @pytest.mark.parametrize("expected_text,description", REQUIRED_TEXT_VALUES,
                             ids=[v[1] for v in REQUIRED_TEXT_VALUES])
    def test_content_present(self, pdf_text, expected_text, description):
        """Verify required text content appears in the PDF."""
        normalized_pdf = normalize_text(pdf_text)
        normalized_expected = normalize_text(expected_text)

        # For currency amounts, also check common formatted variants
        if description == "claim_amount":
            amount_variants = [
                normalize_text("3275"),
                normalize_text("3,275"),
                normalize_text("3,275.00"),
            ]
            found = any(v in normalized_pdf for v in amount_variants)
            assert found, \
                f"Claim amount not found in PDF. Expected '3275' or formatted variant."
        else:
            assert normalized_expected in normalized_pdf, \
                f"Required content '{expected_text}' ({description}) not found in PDF text"


class TestCheckboxes:
    """Test that all required checkboxes are checked correctly."""

    @pytest.mark.parametrize("field_pattern,description,expected,should_check", REQUIRED_CHECKBOXES,
                             ids=[c[1] for c in REQUIRED_CHECKBOXES])
    def test_checkbox_value(self, checkbox_data, field_pattern, description, expected, should_check):
        """Verify checkbox is checked with the correct value."""
        # Find matching checkbox field
        matching_fields = {
            name: val for name, val in checkbox_data.items()
            if field_pattern in name
        }

        if not matching_fields:
            # If no checkboxes found at all, it might be extraction failure
            if not checkbox_data:
                pytest.skip("No checkbox data could be extracted from PDF (XFA extraction may not be supported)")
            pytest.fail(
                f"Checkbox '{description}' (pattern: {field_pattern}) not found. "
                f"Available checkboxes: {list(checkbox_data.keys())}"
            )

        # Check if any matching field has the expected value
        found_correct = False
        found_values = []

        for name, value in matching_fields.items():
            found_values.append(f"{name}={value}")
            if checkbox_value_matches(value, expected):
                found_correct = True
                break

        if should_check:
            assert found_correct, \
                f"Checkbox '{description}': expected value '{expected}', " \
                f"but found: {found_values}"


class TestUncheckedCheckboxes:
    """Test that checkboxes which should NOT be checked are left unchecked."""

    @pytest.mark.parametrize("field_pattern,description", UNCHECKED_CHECKBOXES,
                             ids=[c[1] for c in UNCHECKED_CHECKBOXES])
    def test_checkbox_unchecked(self, checkbox_data, field_pattern, description):
        """Verify checkbox is NOT checked (should be Off or empty)."""
        # Find matching checkbox field
        matching_fields = {
            name: val for name, val in checkbox_data.items()
            if field_pattern in name
        }

        if not matching_fields:
            # If no checkboxes found at all, it might be extraction failure
            if not checkbox_data:
                pytest.skip("No checkbox data could be extracted from PDF")
            # Field not found means it's likely unchecked (not in filled data)
            return

        # Check that none of the matching fields are checked
        for name, value in matching_fields.items():
            is_unchecked = not value or value in ["/Off", "Off", "", "None"]
            assert is_unchecked, \
                f"Checkbox '{description}' should be unchecked, but found: {name}={value}"


class TestEmptyFields:
    """Test that fields which should be empty are left blank."""

    @pytest.mark.parametrize("field_name,description", EMPTY_FIELDS,
                             ids=[f[1] for f in EMPTY_FIELDS])
    def test_field_empty(self, pdf_field_values, field_name, description):
        """Verify field is empty or has minimal placeholder."""
        value = pdf_field_values.get(field_name, "")
        is_empty = not value or value in ["", "None"] or len(value) < 3
        assert is_empty, f"Field '{description}' should be empty, got: '{value}'"
