"""
Tests for medical-intake-form-filling task (MIF-200 Patient Intake Form).

Verifies that the agent correctly fills out the Greenfield Medical Center
Patient Registration & Intake Form based on the provided patient description.

Uses pypdf to extract field values (AcroForm) and pdftotext for visible text.
"""

import subprocess
from pathlib import Path

import pytest

OUTPUT_FILE = Path("/root/intake-filled.pdf")
INPUT_FILE = Path("/root/intake-blank.pdf")


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all visible text from a PDF using pdftotext."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        pytest.fail(f"pdftotext failed: {e}")
    return ""


def get_field_values(pdf_path: Path) -> dict:
    """Extract all AcroForm field values from a PDF."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    fields = reader.get_fields() or {}
    result = {}
    for name, field in fields.items():
        val = field.get("/V", "")
        if val:
            if hasattr(val, "get_object"):
                try:
                    val = str(val.get_object())
                except Exception:
                    val = str(val)
            else:
                val = str(val)
        result[name] = val if val else ""
    return result


def normalise(text: str) -> str:
    return " ".join(text.lower().split())


# ---------------------------------------------------------------------------
# Expected text values that MUST appear in the filled PDF
# ---------------------------------------------------------------------------
REQUIRED_TEXT_VALUES = [
    # Patient info
    ("Marcus Rivera", "patient_name"),
    ("1985-07-14", "patient_dob"),
    ("742 Elm Street", "patient_address"),
    ("Portland", "patient_city"),
    ("97205", "patient_zip"),
    ("5039218734", "patient_phone"),
    ("m.rivera85@outlook.com", "patient_email"),
    # Emergency contact
    ("Sofia Rivera", "emergency_contact_name"),
    ("5039218756", "emergency_phone"),
    # Insurance
    ("BlueCross BlueShield", "insurance_provider"),
    ("BCB-4471923", "insurance_policy_num"),
    ("GRP-88012", "insurance_group_num"),
    # Visit reason keywords
    ("lower back pain", "visit_reason_keyword"),
    ("2026-02-10", "symptom_start_date"),
    # Allergies
    ("Penicillin", "allergy_penicillin"),
    # Medications keywords
    ("Lisinopril", "medication_lisinopril"),
    ("Metformin", "medication_metformin"),
    # Signature
    ("2026-03-15", "signature_date"),
]

# ---------------------------------------------------------------------------
# Checkboxes that MUST be checked (/Yes or equivalent truthy value)
# ---------------------------------------------------------------------------
REQUIRED_CHECKED = [
    ("has_insurance_yes", "has_insurance_yes"),
    ("injury_related_no", "injury_not_related"),
    ("workplace_incident_no", "not_workplace_incident"),
    ("allergies_yes", "has_allergies"),
    ("cond_hypertension", "condition_hypertension"),
    ("cond_diabetes", "condition_diabetes"),
    ("family_heart_yes", "family_heart_disease"),
    ("family_diabetes_yes", "family_diabetes"),
    ("family_cancer_no", "no_family_cancer"),
    ("consent_treatment_yes", "consent_treatment"),
    ("consent_billing_yes", "consent_billing"),
]

# ---------------------------------------------------------------------------
# Checkboxes that must NOT be checked
# ---------------------------------------------------------------------------
REQUIRED_UNCHECKED = [
    ("has_insurance_no", "insurance_no_unchecked"),
    ("injury_related_yes", "injury_yes_unchecked"),
    ("workplace_incident_yes", "workplace_yes_unchecked"),
    ("allergies_no", "allergies_no_unchecked"),
    ("cond_heart_disease", "cond_heart_disease_unchecked"),
    ("cond_asthma", "cond_asthma_unchecked"),
    ("cond_arthritis", "cond_arthritis_unchecked"),
    ("cond_depression", "cond_depression_unchecked"),
    ("cond_cancer", "cond_cancer_unchecked"),
    ("cond_none", "cond_none_unchecked"),
    ("consent_treatment_no", "consent_treatment_no_unchecked"),
    ("consent_billing_no", "consent_billing_no_unchecked"),
]

# ---------------------------------------------------------------------------
# Fields that MUST remain empty (office-use-only)
# ---------------------------------------------------------------------------
EMPTY_FIELDS = [
    ("office_patient_id", "office_patient_id"),
    ("office_physician", "office_physician"),
    ("office_visit_date", "office_visit_date"),
    ("office_intake_nurse", "office_intake_nurse"),
]


# ===== Fixtures =====

@pytest.fixture(scope="module")
def pdf_text():
    if not OUTPUT_FILE.exists():
        pytest.fail(f"Output file not found at {OUTPUT_FILE}")
    text = extract_pdf_text(OUTPUT_FILE)
    if not text:
        pytest.fail("Failed to extract text from PDF")
    return text


@pytest.fixture(scope="module")
def field_vals():
    if not OUTPUT_FILE.exists():
        pytest.fail(f"Output file not found at {OUTPUT_FILE}")
    return get_field_values(OUTPUT_FILE)


# ===== Test classes =====

class TestPDFValid:
    """Verify the output file exists and is a valid, modified PDF."""

    def test_output_exists_and_valid(self, pdf_text):
        assert OUTPUT_FILE.exists(), f"Output not found at {OUTPUT_FILE}"

        with open(OUTPUT_FILE, "rb") as fh:
            header = fh.read(5)
        assert header == b"%PDF-", "Not a valid PDF"

        sz = OUTPUT_FILE.stat().st_size
        assert sz > 1000, f"File too small ({sz} bytes)"

        in_sz = INPUT_FILE.stat().st_size
        out_sz = OUTPUT_FILE.stat().st_size
        if in_sz == out_sz:
            with open(INPUT_FILE, "rb") as f1, open(OUTPUT_FILE, "rb") as f2:
                assert f1.read() != f2.read(), "Output identical to input"

        assert len(pdf_text) > 50, "Extracted text too short"


class TestRequiredContent:
    """Verify all required text values appear in the filled PDF."""

    @pytest.mark.parametrize(
        "expected_text,description",
        REQUIRED_TEXT_VALUES,
        ids=[v[1] for v in REQUIRED_TEXT_VALUES],
    )
    def test_text_present(self, pdf_text, expected_text, description):
        norm_pdf = normalise(pdf_text)
        norm_exp = normalise(expected_text)
        assert norm_exp in norm_pdf, (
            f"Required text '{expected_text}' ({description}) not found in PDF"
        )


class TestCheckedCheckboxes:
    """Verify checkboxes that should be checked ARE checked."""

    @pytest.mark.parametrize(
        "field_name,description",
        REQUIRED_CHECKED,
        ids=[c[1] for c in REQUIRED_CHECKED],
    )
    def test_checkbox_checked(self, field_vals, field_name, description):
        val = field_vals.get(field_name, "")
        truthy = val and val not in ["/Off", "Off", "", "None", "/No", "No"]
        assert truthy, (
            f"Checkbox '{description}' ({field_name}) should be checked, "
            f"but got: '{val}'"
        )


class TestUncheckedCheckboxes:
    """Verify checkboxes that should NOT be checked are unchecked."""

    @pytest.mark.parametrize(
        "field_name,description",
        REQUIRED_UNCHECKED,
        ids=[c[1] for c in REQUIRED_UNCHECKED],
    )
    def test_checkbox_unchecked(self, field_vals, field_name, description):
        val = field_vals.get(field_name, "")
        unchecked = not val or val in ["/Off", "Off", "", "None"]
        assert unchecked, (
            f"Checkbox '{description}' ({field_name}) should be unchecked, "
            f"but got: '{val}'"
        )


class TestEmptyFields:
    """Verify office-use-only fields are left blank."""

    @pytest.mark.parametrize(
        "field_name,description",
        EMPTY_FIELDS,
        ids=[f[1] for f in EMPTY_FIELDS],
    )
    def test_field_empty(self, field_vals, field_name, description):
        val = field_vals.get(field_name, "")
        is_empty = not val or val in ["", "None"] or len(val) < 3
        assert is_empty, f"Office field '{description}' should be empty, got: '{val}'"
