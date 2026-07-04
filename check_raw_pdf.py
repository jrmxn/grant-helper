import fitz
import sys
import os

# Append the current directory so we can import main
sys.path.append(os.getcwd())
from main import export_doc_to_pdf

pdf_path = "test_download.pdf"
export_doc_to_pdf("1iQ9cfj8UKGKzXrm4fDiPTa0-r2Ux5l6kOSqXTmBvEtY", pdf_path, "driveapiproject-498815-21dc986903e9.json")

doc = fitz.open(pdf_path)

annot_types = set()
for page in doc:
    for annot in page.annots() or []:
        annot_types.add(annot.type[1])

print(f"Annotation types found in raw PDF: {annot_types}")

drawing_colors = set()
for page in doc:
    paths = page.get_drawings()
    for p in paths:
        if p.get("fill_opacity") is not None and p["fill_opacity"] > 0 and p.get("fill") is not None:
            drawing_colors.add(tuple(p["fill"]))

print(f"Drawing fill colors found in raw PDF: {drawing_colors}")

# Check text spans for background colors
text_bg_colors = set()
for page in doc:
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if "lines" in b:
            for l in b["lines"]:
                for s in l["spans"]:
                    # PyMuPDF doesn't directly expose text background color in get_text("dict")
                    # Text background is usually drawn as a path before the text.
                    pass

doc.close()
