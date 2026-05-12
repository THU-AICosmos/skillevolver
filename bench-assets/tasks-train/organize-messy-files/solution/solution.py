#!/usr/bin/env python3
"""
Oracle solution for organize-messy-files training variant.

Uses a fixed mapping from document IDs to subject folders (machine_learning,
climate_change, neuroscience, ancient_history). The documents are generated
during image build; at solve time we simply move each file into its subject
folder without renaming it.
"""

import shutil
from pathlib import Path

SUBJECT_TO_PAPERS: dict[str, list[str]] = {
    "machine_learning": [
        "DOC-1ZXOI6.pdf",
        "DOC-5FDHJK.pdf",
        "DOC-AK1VRJ.pdf",
        "DOC-CUZREN.pdf",
        "DOC-FNO6B9.pdf",
        "DOC-G8F1CB.pdf",
        "DOC-HBRPOI.pdf",
        "DOC-HYF9SX.pdf",
        "DOC-K8PK3Y.pdf",
        "DOC-KXWNRE.pdf",
        "DOC-M80O2R.pdf",
        "DOC-MECOSF.pdf",
        "DOC-NVGFYG.pdf",
        "DOC-OGYR3X.pdf",
        "DOC-QIP98Q.pdf",
        "DOC-R9OUDO.pdf",
        "DOC-UN5Z3J.pdf",
        "DOC-WWQC38.pdf",
    ],
    "climate_change": [
        "DOC-1EYY37.pdf",
        "DOC-1N8MTZ.pdf",
        "DOC-5N8I4P.pdf",
        "DOC-87AU5B.pdf",
        "DOC-AQ6L6G.pdf",
        "DOC-CVE6PR.pdf",
        "DOC-FF5E8I.pdf",
        "DOC-HXTPDP.pdf",
        "DOC-I49KQ7.pdf",
        "DOC-OAEDOE.pdf",
        "DOC-OEVB9O.pdf",
        "DOC-Q9AH8R.pdf",
        "DOC-T6MJXK.pdf",
        "DOC-VHS1K3.pdf",
        "DOC-X272HP.pdf",
    ],
    "neuroscience": [
        "DOC-3S195J.pdf",
        "DOC-3UEA3G.pdf",
        "DOC-40MGG1.pdf",
        "DOC-DKYAYQ.pdf",
        "DOC-DZVGPM.pdf",
        "DOC-EPZHPC.pdf",
        "DOC-F07UQN.pdf",
        "DOC-GD8AFP.pdf",
        "DOC-K054NZ.pdf",
        "DOC-KD6FLE.pdf",
        "DOC-M82I1L.pdf",
        "DOC-MSND8D.pdf",
        "DOC-R3PE29.pdf",
        "DOC-UDD467.pdf",
        "DOC-UPQZIT.pdf",
        "DOC-W103DG.pdf",
    ],
    "ancient_history": [
        "DOC-28T7A9.pdf",
        "DOC-9AHEJ8.pdf",
        "DOC-9JRSNV.pdf",
        "DOC-CTXCWN.pdf",
        "DOC-CX9J1I.pdf",
        "DOC-E8N6QI.pdf",
        "DOC-F1RCAV.pdf",
        "DOC-IQK291.pdf",
        "DOC-NQ65QD.pdf",
        "DOC-PGW90J.pdf",
        "DOC-PKL0BL.pdf",
        "DOC-TGIQHG.pdf",
        "DOC-V0PRKG.pdf",
        "DOC-WEPXSK.pdf",
    ],
}

EXTRA_FILES_BY_SUBJECT: dict[str, list[str]] = {
    "machine_learning": ["NeurIPS_talk.pptx", "ICML_workshop.pptx"],
    "climate_change": ["ipcc_summary_draft.docx"],
    "neuroscience": ["lab_protocol_ephys.docx", "grant_proposal_brain.docx"],
    "ancient_history": ["archaeology_lecture.pptx", "artifact_catalog.xlsx"],
}

SUBJECT_TO_FILES: dict[str, list[str]] = {
    subject: papers + EXTRA_FILES_BY_SUBJECT.get(subject, [])
    for subject, papers in SUBJECT_TO_PAPERS.items()
}

SOURCE_DIR_CANDIDATES = [
    Path("/root/documents/unsorted"),
    Path("/root/documents"),
    Path("/root"),
    Path(__file__).resolve().parent.parent / "environment" / "data",
]


def resolve_source_dir() -> Path:
    for candidate in SOURCE_DIR_CANDIDATES:
        if candidate.is_dir():
            return candidate
    return Path.cwd()


def normalize_filename(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".pdf"):
        return f"{name[:-4]}.pdf"
    if lower.endswith(".pptx"):
        return f"{name[:-5]}.pptx"
    if lower.endswith(".docx"):
        return f"{name[:-5]}.docx"
    if lower.endswith(".xlsx"):
        return f"{name[:-5]}.xlsx"
    return name


def resolve_file(name: str, search_roots: list[Path]) -> Path:
    normalized = normalize_filename(name)
    for root in search_roots:
        candidate = root / normalized
        if candidate.exists():
            return candidate

    # Fallback: search recursively
    for root in search_roots:
        for candidate in root.rglob("*"):
            if candidate.is_file() and candidate.name == normalized:
                return candidate

    raise FileNotFoundError(
        f"Could not find {name} under {', '.join(str(r) for r in search_roots)}"
    )


def organize_documents() -> None:
    source_dir = resolve_source_dir()
    target_root = source_dir.parent if source_dir.name == "unsorted" else source_dir

    search_roots = [source_dir, target_root]
    search_roots.extend(target_root / folder for folder in SUBJECT_TO_FILES)

    moved = 0
    already_sorted = 0

    for subject, files in SUBJECT_TO_FILES.items():
        destination = target_root / subject
        destination.mkdir(parents=True, exist_ok=True)

        for filename in files:
            src_path = resolve_file(filename, search_roots)
            dest_path = destination / src_path.name

            if dest_path.resolve() == src_path.resolve():
                already_sorted += 1
                continue

            if dest_path.exists():
                already_sorted += 1
                continue

            shutil.move(str(src_path), str(dest_path))
            moved += 1

    total = sum(len(files) for files in SUBJECT_TO_FILES.values())
    print(
        f"Organized files into {len(SUBJECT_TO_FILES)} folders under {target_root}. "
        f"Moved {moved}, already sorted {already_sorted}, expected {total} total."
    )


if __name__ == "__main__":
    organize_documents()
