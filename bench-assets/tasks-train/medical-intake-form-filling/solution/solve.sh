#!/bin/bash
set -e

cat > /tmp/populate_intake.py << 'PYEOF'
#!/usr/bin/env python3
"""
Solution for medical intake form filling task.
Populates the Greenfield Medical Center MIF-200 intake form.
"""

import os
import shutil
from pypdf import PdfReader, PdfWriter

SRC_PDF = "/root/intake-blank.pdf"
DST_PDF = "/root/intake-filled.pdf"


def populate_form():
    print("Reading blank intake form...")
    rdr = PdfReader(SRC_PDF)
    wrt = PdfWriter()
    wrt.append(rdr)

    # --- text entries ---
    txt_entries = {
        # Section 1 - patient info
        "patient_full_name": "Marcus Rivera",
        "patient_dob": "1985-07-14",
        "patient_address": "742 Elm Street",
        "patient_city": "Portland",
        "patient_state": "OR",
        "patient_zip": "97205",
        "patient_phone": "5039218734",
        "patient_email": "m.rivera85@outlook.com",

        # Section 2 - emergency contact
        "emergency_name": "Sofia Rivera",
        "emergency_relationship": "Wife",
        "emergency_phone": "5039218756",

        # Section 3 - insurance
        "insurance_provider": "BlueCross BlueShield",
        "insurance_policy_num": "BCB-4471923",
        "insurance_group_num": "GRP-88012",
        "insurance_subscriber": "Marcus Rivera",

        # Section 4 - visit reason
        "visit_reason": "Persistent lower back pain and numbness in left leg.",
        "symptom_start_date": "2026-02-10",

        # Page 2 header
        "page2_patient_name": "Marcus Rivera",

        # Section 5 - allergies & medications
        "allergy_list": "Penicillin, Sulfa drugs",
        "current_medications": "Lisinopril 10mg daily, Metformin 500mg twice daily",

        # Section 7 - signature
        "signature_name": "Marcus Rivera",
        "signature_date": "2026-03-15",
    }

    # --- checkbox entries ---
    chk_entries = {
        # 3a insurance yes
        "has_insurance_yes": "/Yes",
        # 4c injury - no
        "injury_related_no": "/Yes",
        # 4d workplace - no
        "workplace_incident_no": "/Yes",
        # 5a allergies yes
        "allergies_yes": "/Yes",
        # 5c conditions
        "cond_hypertension": "/Yes",
        "cond_diabetes": "/Yes",
        # 6a family heart yes
        "family_heart_yes": "/Yes",
        # 6b family diabetes yes
        "family_diabetes_yes": "/Yes",
        # 6c family cancer no
        "family_cancer_no": "/Yes",
        # 7a consent yes
        "consent_treatment_yes": "/Yes",
        # 7b billing yes
        "consent_billing_yes": "/Yes",
    }

    merged = {**txt_entries, **chk_entries}

    print(f"Filling {len(txt_entries)} text fields and {len(chk_entries)} checkboxes...")
    for pg_idx, pg in enumerate(wrt.pages):
        try:
            wrt.update_page_form_field_values(pg, merged)
        except Exception as exc:
            print(f"  Warning on page {pg_idx}: {exc}")

    print(f"Saving filled form to {DST_PDF}...")
    with open(DST_PDF, "wb") as fh:
        wrt.write(fh)

    # Copy to verifier dir if available
    log_dir = "/logs/verifier"
    if os.path.exists("/logs"):
        os.makedirs(log_dir, exist_ok=True)
        shutil.copy(DST_PDF, os.path.join(log_dir, "intake-filled.pdf"))
        print("Copied to verifier folder.")

    print("Done.")


if __name__ == "__main__":
    populate_form()
PYEOF

python3 /tmp/populate_intake.py
echo "Intake form filled successfully."
