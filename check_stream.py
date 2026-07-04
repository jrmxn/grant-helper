import fitz

pdf_path = "test_download.pdf"
doc = fitz.open(pdf_path)

for page_num in range(len(doc)):
    page = doc[page_num]
    for xref in page.get_contents():
        stream = doc.xref_stream(xref)
        if b"rg" in stream:
            lines = stream.split(b"\n")
            for i, line in enumerate(lines):
                if b" rg" in line and not (b"0 0 0 rg" in line or b"1 1 1 rg" in line):
                    print(f"Page {page_num} Line {i-2}: {lines[i-2] if i >= 2 else b''}")
                    print(f"Page {page_num} Line {i-1}: {lines[i-1] if i >= 1 else b''}")
                    print(f"Page {page_num} Line {i}: {line}")
                    print(f"Page {page_num} Line {i+1}: {lines[i+1] if i+1 < len(lines) else b''}")
                    print("-" * 40)

doc.close()
