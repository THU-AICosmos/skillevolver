#!/bin/bash
set -e

cat > /tmp/fill_defendant_claim.py << 'PYSRC'
#!/usr/bin/env python3
"""Oracle for the court-form-filling training variant (SC-120).

Populates the California "Defendant's Claim and ORDER to Go to Small
Claims Court" form on behalf of Marcus Rivera, who is filing a
defendant's counterclaim against Thornwood Auto Repair LLC for damage
caused during a botched transmission service.
"""

from dataclasses import dataclass
from pathlib import Path
from pypdf import PdfReader, PdfWriter


BLANK_PATH = Path("/root/sc120-blank.pdf")
FILLED_PATH = Path("/root/sc120-filled.pdf")
VERIFIER_COPY = Path("/logs/verifier/sc120-filled.pdf")


@dataclass(frozen=True)
class CaseRecord:
    """All the values the defendant needs to communicate on SC-120."""

    # Defendant (the person filing SC-120 -- that's "us")
    def_name: str
    def_phone: str
    def_street: str
    def_city: str
    def_state: str
    def_zip: str

    # Plaintiff (the party we are suing back)
    pl_name: str
    pl_phone: str
    pl_street: str
    pl_city: str
    pl_state: str
    pl_zip: str

    # Claim narrative (item 3)
    claim_amount: str
    claim_reason: str
    claim_start: str
    claim_end: str
    claim_calc: str

    # Signature block
    sign_date: str


CASE = CaseRecord(
    def_name="Marcus Rivera",
    def_phone="5103340912",
    def_street="1428 Linden St",
    def_city="Oakland",
    def_state="CA",
    def_zip="94607",
    pl_name="Thornwood Auto Repair LLC",
    pl_phone="5105557432",
    pl_street="2210 International Blvd",
    pl_city="Oakland",
    pl_state="CA",
    pl_zip="94606",
    claim_amount="3275",
    claim_reason=(
        "Botched transmission service caused further damage to my vehicle, "
        "requiring towing and a second corrective repair at another shop."
    ),
    claim_start="2025-11-12",
    claim_end="2026-02-04",
    claim_calc=(
        "$475 tow invoice + $2800 corrective-repair invoice from a second "
        "mechanic. Receipts retained."
    ),
    sign_date="2026-03-07",
)


# -- SC-120 field paths --------------------------------------------------
# Prefix shortcuts keep the long qualified names readable.
P2_PL = "SC-120[0].Page2[0].List1[0].item1[0]."
P2_DF = "SC-120[0].Page2[0].List2[0].item2[0]."
P2_L3 = "SC-120[0].Page2[0].List3[0]."
P3_Q4 = "SC-120[0].Page3[0].List4[0].item4[0]."  # asked plaintiff to pay
P3_Q5 = "SC-120[0].Page3[0].List5[0].item5[0]."  # attorney-client fee dispute
P3_Q6 = "SC-120[0].Page3[0].List6[0].item6[0]."  # suing a public entity
P3_Q7 = "SC-120[0].Page3[0].List7[0].item7[0]."  # >12 claims in 12 months
P3_SG = "SC-120[0].Page3[0].List10[0].Li1[0]."   # signature block


def build_text_fields(rec: CaseRecord) -> dict:
    """Build every /Tx (text) field we want written onto SC-120."""
    return {
        # -- Item 1: the Plaintiff being sued (Thornwood Auto Repair LLC) --
        # FillText19 = primary plaintiff name, FillText7 = primary phone
        P2_PL + "FillText19[0]": rec.pl_name,
        P2_PL + "FillText7[0]": rec.pl_phone,
        P2_PL + "PlaintiffAdress[0]": rec.pl_street,
        P2_PL + "PlaintiffCity[0]": rec.pl_city,
        P2_PL + "PlaintiffState[0]": rec.pl_state,
        P2_PL + "PlaintiffZip[0]": rec.pl_zip,

        # -- Item 2: the Defendant (us, Marcus Rivera) --
        P2_DF + "DefName[0]": rec.def_name,
        P2_DF + "DefPhone[0]": rec.def_phone,
        P2_DF + "DefAddress[0]": rec.def_street,
        P2_DF + "DefCity[0]": rec.def_city,
        P2_DF + "DefState[0]": rec.def_state,
        P2_DF + "DefZip[0]": rec.def_zip,

        # -- Item 3: the money owed and why --
        P2_L3 + "FillText63[0]": rec.claim_amount,
        P2_L3 + "Lia[0].FillText64[0]": rec.claim_reason,
        # Item 3b "time period" sub-fields
        P2_L3 + "Lib[0].FillText67[0]": rec.claim_start,  # Date started
        P2_L3 + "Lib[0].FillText68[0]": rec.claim_end,    # Through
        # Item 3c: how the amount was calculated
        P2_L3 + "Lic[0].FillText70[0]": rec.claim_calc,

        # -- Signature block (item 10) --
        P3_SG + "Field1[0]": rec.def_name,   # prints defendant name
        P3_SG + "Date1[0]": rec.sign_date,   # date next to name
        P3_SG + "Date2[0]": rec.sign_date,   # date next to signature line
    }


def build_checkbox_fields() -> dict:
    """Build every /Btn field we want toggled on SC-120.

    Each yes/no question on SC-120 is a pair of sibling checkboxes:
    ``ChN[0]`` is the "Yes" option and ``ChN[1]`` is the "No" option.
    Setting the desired option to ``/1`` selects it; the other sibling
    stays at its default ``Off`` value.
    """
    return {
        # Q4: Have you asked the Plaintiff to pay? -> Yes
        P3_Q4 + "Ch1[0]": "/1",

        # Q5: Is your claim about an attorney-client fee dispute? -> No
        P3_Q5 + "Ch2[1]": "/2",

        # Q6: Are you suing a public entity? -> No
        P3_Q6 + "Ch3[1]": "/2",

        # Q7: Filed >12 small claims in the last 12 months? -> No
        P3_Q7 + "Ch4[1]": "/2",
    }


def apply_to_writer(writer: PdfWriter, values: dict) -> None:
    """Apply ``values`` to every page of ``writer``."""
    for page_index, page in enumerate(writer.pages):
        try:
            writer.update_page_form_field_values(page, values)
        except Exception as exc:  # pypdf may warn on unknown fields
            print(f"  [page {page_index}] warning: {exc}")


def copy_to_verifier() -> None:
    """Mirror the filled PDF to /logs/verifier for manual review."""
    verifier_dir = VERIFIER_COPY.parent
    if verifier_dir.parent.exists():
        verifier_dir.mkdir(parents=True, exist_ok=True)
        VERIFIER_COPY.write_bytes(FILLED_PATH.read_bytes())
        print(f"  Mirrored to {VERIFIER_COPY}")


def run() -> None:
    banner = "=" * 60
    print(banner)
    print("SC-120 Defendant's Claim -- Oracle Fill")
    print(banner)

    print("\n[step 1/4] loading blank form")
    reader = PdfReader(str(BLANK_PATH))
    print(f"  pages: {len(reader.pages)}")

    # IMPORTANT: XFA templates survive only via append(); add_page()
    # copies the raw page but drops the /XFA array -> rendered PDFs
    # come out blank in most viewers.
    writer = PdfWriter()
    writer.append(reader)

    print("\n[step 2/4] assembling field payload")
    text_fields = build_text_fields(CASE)
    checkbox_fields = build_checkbox_fields()
    all_fields = {**text_fields, **checkbox_fields}
    print(f"  text fields:     {len(text_fields)}")
    print(f"  checkbox fields: {len(checkbox_fields)}")

    print("\n[step 3/4] updating pages")
    apply_to_writer(writer, all_fields)

    print("\n[step 4/4] writing output")
    with FILLED_PATH.open("wb") as out:
        writer.write(out)
    print(f"  wrote {FILLED_PATH}")

    copy_to_verifier()

    print(f"\n{banner}\nDone.\n{banner}")


if __name__ == "__main__":
    run()
PYSRC

python3 /tmp/fill_defendant_claim.py
echo "Solution complete."
