"""Builds one ready-to-upload folder per fictional patient: demo_uploads/<Patient_Name>/ with the pictures in the order to upload them.

    python data/synthetic/make_demo_folders.py

The folders hold the PHOTO versions (tilted, shadowed, like a phone picture) or, for a document with more than one page, the PDF.
Files are copies of data/synthetic/rendered/*, which `render.py` and `render_labels.py` make. The folder is git-ignored; this script rebuilds it.
Everything is fictional."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYN = ROOT / "data" / "synthetic"
REND = SYN / "rendered"
OUT = ROOT / "demo_uploads"

# patient folder -> (data folder, [(document id, file name stem, what to look for)])
PATIENTS = {
    "Sunita_Deshmukh": ("sunita", [
        ("S1", "01_allergy_card", "allergy listed: NSAIDs (a drug class)"),
        ("S2", "02_orthopaedic_prescription", "5 medicines, follow-up in 2 weeks, duplicate-brand paracetamol starts here"),
        ("S3", "03_mri_lumbar_spine_report", "4 imaging findings as results, with sources; nothing interpreted"),
        ("S4", "04_physiotherapy_plan", "instructions, written warning signs with levels, follow-up in 4 weeks"),
        ("S6", "05_lab_report", "3 lab values shown as printed with their reference range"),
        ("S5", "06_second_doctor_prescription", "Diclofenac flagged as an NSAID-family match; paracetamol duplicate question"),
    ]),
    "Ramesh_Kulkarni": ("ramesh", [
        ("R4", "01_allergy_card", "allergy listed: penicillin"),
        ("R1", "02_clinic_prescription", "4 medicines and a follow-up"),
        ("R2", "03_discharge_summary", "Atorvastatin missing from the new list: omission question; 2 pages, so a PDF"),
        ("R5", "04_second_doctor_prescription", "Amoxicillin flagged against the penicillin allergy"),
        ("R7", "05_blurry_copy", "a page with a smudged strength"),
    ]),
    "Margaret_Ellis": ("margaret", [
        ("M1", "01_pharmacy_label", "a medicine label"),
        ("M2", "02_discharge_note", "a discharge note"),
        ("M3", "03_new_antibiotic", "a new antibiotic against a class allergy"),
    ]),
    "Hans_Weber": ("hans", [
        ("H1", "01_medikationsplan", "a German medication plan"),
        ("H2", "02_arztbrief", "a German doctor's letter"),
        ("H3", "03_unknown_brand", "a brand the reference list does not know: shown as could not check, never as clear"),
    ]),
}


def pages_in(doc_id: str, folder: str) -> int:
    txt = next((SYN / folder / "docs").glob(f"{doc_id}_*.txt"), None)
    return len(txt.read_text(encoding="utf-8").split("\f")) if txt else 1


def main() -> int:
    if not (REND / "S1_photo.png").exists():
        subprocess.check_call([sys.executable, str(SYN / "render.py")])
    if OUT.exists():
        shutil.rmtree(OUT)
    lines = ["Upload order for each fictional patient (all data is fictional; never upload real records to the live model).", ""]
    for name, (folder, docs) in PATIENTS.items():
        d = OUT / name
        d.mkdir(parents=True)
        lines.append(f"{name}")
        for doc_id, stem, note in docs:
            multi = pages_in(doc_id, folder) > 1
            src = REND / (f"{doc_id}.pdf" if multi else f"{doc_id}_photo.png")
            if not src.exists():
                continue
            target = d / (stem + src.suffix)
            shutil.copy2(src, target)
            lines.append(f"  {target.name:<42} {note}")
        lines.append("")
    (OUT / "README.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"built {OUT}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
