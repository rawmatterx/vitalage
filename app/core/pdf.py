"""The one-page PDF summary of a result (the "Download summary" button).

It holds the date, age and results of one blood test, and no name or email:
the person chooses whether to show it to a doctor.
"""

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from phenoage.vitalage import VERSION

INK = colors.HexColor("#12181c")
MUTED = colors.HexColor("#74828a")
LINE = colors.HexColor("#dbe2e5")


def _signed(x):
    s = "%+.1f" % x
    return "0.0" if s in ("+0.0", "-0.0") else s


def summary_pdf(r, test_date, fasting):
    """r: the dict from science.compute(). Returns the PDF as bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="VitalAge summary", author="VitalAge")
    styles = getSampleStyleSheet()
    h1, body, small = styles["Title"], styles["BodyText"], styles["BodyText"].clone("small")
    h1.alignment = 0
    small.fontSize, small.leading, small.textColor = 8.5, 11, MUTED
    h2 = styles["Heading3"]

    fasting_text = {"yes": "fasting", "no": "not fasting"}.get(fasting, "fasting not known")
    story = [
        Paragraph("VitalAge summary", h1),
        Paragraph("Blood test on %s, at age %.1f, %s." % ("%d %s" % (test_date.day, test_date.strftime("%B %Y")),
                                                          r["age"], fasting_text), body),
        Spacer(1, 6 * mm),
    ]

    if r["complete"]:
        rows = [["Internal age", "%.1f years" % r["internal_age"]],
                ["Internal age vs calendar age", "%s years" % _signed(r["gap"])],
                ["Pace estimate (one test)", "%.2f  (typical at this age %.2f)" % (r["pace"], r["typical_pace"])],
                ["PhenoAge (published reference)", "%.1f years" % r["phenoage"]]]
    else:
        rows = [["Internal age (range)", "%.1f to %.1f years" % (r["internal_low"], r["internal_high"])],
                ["Vs calendar age", "%s to %s years" % (_signed(r["gap_low"]), _signed(r["gap_high"]))],
                ["PhenoAge (range)", "%.1f to %.1f years" % (r["phenoage_low"], r["phenoage_high"])],
                ["Not entered", ", ".join(r["missing"])]]
    story.append(_table(rows, (70 * mm, 100 * mm)))

    if r["complete"]:
        story += [Spacer(1, 6 * mm), Paragraph("What moves internal age", h2),
                  Paragraph("Years each marker adds (+) or removes (-), compared with a typical "
                            "healthy adult of the same age.", small), Spacer(1, 2 * mm)]
        levers = [["Typical healthy adult", _signed(r["baseline_gap"])]]
        levers += [[lever["label"], _signed(lever["years"])] for lever in r["levers"]]
        story.append(_table(levers, (120 * mm, 50 * mm)))

    if r["warnings"]:
        story += [Spacer(1, 5 * mm), Paragraph("Notes", h2)]
        story += [Paragraph(escape(w), small) for w in r["warnings"]]

    story += [Spacer(1, 8 * mm), Paragraph(
        "Internal age estimates how old the body looks inside from 9 routine blood markers. "
        "It tracks DNA-methylation aging but is not a DNA test. VitalAge %s is a beta research "
        "measure built on US data and not yet validated in Indian adults. "
        "<b>It is not a diagnosis</b>: talk to a doctor about any value that worries you. "
        "A pace you can trust needs 3 tests over at least a year." % VERSION, small)]
    doc.build(story)
    return buf.getvalue()


def _table(rows, widths):
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
    ]))
    return t
