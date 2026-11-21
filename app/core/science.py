"""The bridge between the web pages and the phenoage science package.

The pages only deal with "values as printed on the report". This module turns
them into results with the same functions the command line uses, so the web
app and `python -m phenoage` always agree.
"""

from phenoage.core import MARKERS, phenoage_from_canonical
from phenoage.internal import internal_age_from_canonical, internal_age_range
from phenoage.partial import MAX_MISSING, NORMAL_RANGES, phenoage_range_from_canonical
from phenoage.units import factor, to_canonical

# How each marker is named on the form, and the units offered (the first is
# the usual one on Indian reports). Same choices as web/vitalage.html.
MARKER_INFO = {
    "albumin": ("Albumin", ["g/dL", "g/L"]),
    "creatinine": ("Creatinine", ["mg/dL", "µmol/L"]),
    "glucose": ("Glucose (fasting)", ["mg/dL", "mmol/L"]),
    "crp": ("CRP (hs-CRP)", ["mg/L", "mg/dL"]),
    "lymphocyte_pct": ("Lymphocytes", ["%"]),
    "mcv": ("MCV", ["fL"]),
    "rdw": ("RDW", ["%"]),
    "alp": ("ALP (alkaline phosphatase)", ["U/L", "IU/L"]),
    "wbc": ("WBC (total count)", ["cells/cumm", "10^3/µL", "10^9/L"]),
}


def label(marker):
    return MARKER_INFO[marker][0]


def usual_range(marker, unit):
    """The usual lab range for a marker, in the unit the person entered."""
    lo, hi = (v / factor(marker, unit) for v in NORMAL_RANGES[marker])
    return lo, hi


def fmt(x):
    """Short number for display: 4.3, 112, 8400, 0.35."""
    if abs(x) >= 100:
        return "%g" % round(x)
    return "%g" % round(x, 2)


def review_rows(report):
    """One row per marker for the Review screen, flagging values outside the usual range."""
    rows = []
    for m in MARKERS:
        if m not in report:
            rows.append({"marker": m, "label": label(m), "missing": True})
            continue
        value, unit = report[m]
        lo, hi = usual_range(m, unit)
        flag = "low" if value < lo else "high" if value > hi else ""
        rows.append({"marker": m, "label": label(m), "missing": False, "value": fmt(value),
                     "unit": unit, "range": "%s to %s" % (fmt(lo), fmt(hi)), "flag": flag})
    return rows


def compute(age, report):
    """All results for the Results screen. `report` maps marker -> (value, unit),
    with at most 3 markers left out."""
    known = {m: to_canonical(m, *report[m]) for m in report}
    missing = [m for m in MARKERS if m not in known]
    if len(missing) > MAX_MISSING:
        raise ValueError("At most %d markers can be missing." % MAX_MISSING)

    if missing:
        lo, hi = internal_age_range(age, known)
        pheno = phenoage_range_from_canonical(age, known)
        return {
            "complete": False,
            "age": age,
            "missing": [label(m) for m in missing],
            "internal_low": lo, "internal_high": hi,
            "gap_low": lo - age, "gap_high": hi - age,
            "phenoage_low": pheno.low, "phenoage_high": pheno.high,
            "warnings": pheno.warnings,
        }

    inner = internal_age_from_canonical(age, known)
    pheno = phenoage_from_canonical(age, known)
    biggest = max([abs(y) for y in inner.contributions.values()] + [abs(inner.baseline_gap), 0.1])
    # Bar widths as a % of the whole track; the centre line is at 50%.
    levers = [{"label": label(m), "years": y, "width": round(50 * abs(y) / biggest, 1)}
              for m, y in sorted(inner.contributions.items(), key=lambda kv: -abs(kv[1]))]
    warnings = list(inner.warnings)
    warnings += [w for w in pheno.warnings if w not in warnings and "CRP" not in w]
    return {
        "complete": True,
        "age": age,
        "internal_age": inner.internal_age,
        "gap": inner.gap,
        "pace": inner.pace,
        "typical_pace": inner.typical_pace,
        "baseline_gap": inner.baseline_gap,
        "baseline_width": round(50 * abs(inner.baseline_gap) / biggest, 1),
        "phenoage": pheno.phenoage,
        "levers": levers,
        "warnings": warnings,
    }
