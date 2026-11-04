"""Write examples/sample_lab_report.pdf: a made-up report for trying the import.

    python3 examples/make_sample_report.py

The layout follows a typical Indian lab report (test, result, unit,
reference interval in columns) and includes lines the importer must skip:
post-prandial glucose, RDW-SD, absolute lymphocyte count, A/G ratio.
Plain-Python PDF writer, no packages needed.
"""

import os

COLUMNS = (50, 270, 340, 420)

ROWS = [
    ("title", "EXAMPLE DIAGNOSTICS - SAMPLE REPORT (MADE-UP DATA, NOT A REAL PERSON)"),
    ("text", "Patient: Example Person    Age/Sex: 42 Y / M    Collected: 25/10/2026"),
    ("gap", ""),
    ("head", "HAEMATOLOGY - COMPLETE BLOOD COUNT"),
    ("row", ("Test", "Result", "Unit", "Biological Ref. Interval")),
    ("row", ("Haemoglobin", "14.2", "g/dL", "13.0 - 17.0")),
    ("row", ("Total Leucocyte Count (TLC)", "6,800", "/cumm", "4000 - 11000")),
    ("head", "Differential Leucocyte Count (DLC)"),
    ("row", ("Neutrophils", "58", "%", "40 - 80")),
    ("row", ("Lymphocytes", "32", "%", "20 - 40")),
    ("row", ("Absolute Lymphocyte Count", "2176", "/cumm", "1000 - 3000")),
    ("row", ("MCV", "88.0", "fL", "83 - 101")),
    ("row", ("MCH", "29.5", "pg", "27 - 32")),
    ("row", ("RDW-CV", "13.1", "%", "11.6 - 14.0")),
    ("row", ("RDW-SD", "42.1", "fL", "39 - 46")),
    ("gap", ""),
    ("head", "BIOCHEMISTRY"),
    ("row", ("Glucose Fasting (FBS)", "95", "mg/dL", "70 - 100")),
    ("row", ("Glucose Post Prandial (PPBS)", "128", "mg/dL", "70 - 140")),
    ("row", ("Creatinine, Serum", "0.90", "mg/dL", "0.7 - 1.3")),
    ("row", ("Albumin, Serum", "4.3", "g/dL", "3.5 - 5.2")),
    ("row", ("Globulin", "2.9", "g/dL", "2.0 - 3.5")),
    ("row", ("A/G Ratio", "1.48", "", "1.0 - 2.1")),
    ("row", ("Alkaline Phosphatase (ALP)", "78", "U/L", "40 - 129")),
    ("row", ("hs-CRP", "1.2", "mg/L", "< 3.0")),
    ("gap", ""),
    ("text", "This is sample data for testing VitalAge. It is not a medical report."),
]


def esc(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def content_stream():
    out, y = [], 790
    for kind, data in ROWS:
        if kind == "gap":
            y -= 10
            continue
        size, font = (12, "F2") if kind in ("title", "head") else (10, "F1")
        cells = [(COLUMNS[0], data)] if isinstance(data, str) else list(zip(COLUMNS, data))
        for x, text in cells:
            if text:
                out.append("BT /%s %d Tf %d %d Td (%s) Tj ET" % (font, size, x, y, esc(text)))
        y -= 18
    return "\n".join(out).encode("latin-1")


def write_pdf(path):
    stream = content_stream()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        data += b"%010d 00000 n \n" % off
    data += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    with open(path, "wb") as f:
        f.write(data)


def report_lines():
    """The text lines as a PDF reader rebuilds them (columns joined by two spaces)."""
    lines = []
    for kind, data in ROWS:
        if kind == "gap":
            continue
        lines.append(data if isinstance(data, str) else "  ".join(c for c in data if c))
    return lines


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_lab_report.pdf")
    write_pdf(out)
    print("Wrote " + out)
