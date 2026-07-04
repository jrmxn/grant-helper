import fitz

pdf_path = "/home/mcintosh/Cloud/Gdocs/2026/2026-00-00_r01_renewal/wip/03_research_strategy_2026-07-03T16.pdf"
doc = fitz.open(pdf_path)

annot_types = set()
for page in doc:
    for annot in page.annots():
        annot_types.add(annot.type[1])

print(f"Annotation types found: {annot_types}")

# Also check for drawings (filled rectangles)
drawing_colors = set()
for page in doc:
    paths = page.get_drawings()
    for p in paths:
        if p.get("fill_opacity") is not None and p["fill_opacity"] > 0 and p.get("fill") is not None:
            drawing_colors.add(tuple(p["fill"]))

print(f"Drawing fill colors found: {drawing_colors}")

doc.close()
