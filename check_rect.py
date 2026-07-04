import fitz

pdf_path = "test_download.pdf"
doc = fitz.open(pdf_path)
page = doc[72]
for xref in page.get_contents():
    stream = doc.xref_stream(xref)
    lines = stream.split(b"\n")
    for i, line in enumerate(lines):
        if b"1 1 0 rg" in line:
            for j in range(i, min(i+10, len(lines))):
                print(f"Line {j}: {lines[j]}")
            break
doc.close()
