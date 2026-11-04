"""PhenoAge when some markers are missing: a range instead of a number.

Instead of guessing a missing value, assume only that it lies inside a
typical adult lab reference interval, and report the lowest and highest
PhenoAge that assumption allows. Because PhenoAge is a straight line in the
weighted marker sum (see explain.py), the extremes sit at the interval ends
and the range is exact, not simulated.

The middle estimate puts each missing marker at the typical healthy value
from explain.REFERENCE_PROFILE.

The intervals below are common adult reference intervals printed on lab
reports, in canonical units. Your lab's own interval may differ, and a value
outside it (for example CRP above 10 mg/L during an infection) would put
PhenoAge outside the range.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .core import MARKERS, phenoage_from_canonical
from .explain import REFERENCE_PROFILE, marker_years
from .units import factor, to_canonical

MAX_MISSING = 3

NORMAL_RANGES = {
    "albumin": (35.0, 50.0),          # 3.5-5.0 g/dL
    "creatinine": (0.6 * 88.42, 1.3 * 88.42),     # 0.6-1.3 mg/dL
    "glucose": (70 / 18.016, 100 / 18.016),       # 70-100 mg/dL fasting
    "crp": (0.02, 1.0),               # 0.2-10 mg/L
    "lymphocyte_pct": (20.0, 40.0),
    "mcv": (80.0, 100.0),
    "rdw": (11.5, 14.5),
    "alp": (40.0, 130.0),
    "wbc": (4.0, 11.0),               # 4,000-11,000 cells/cumm
}


@dataclass
class PhenoAgeRange:
    chronological_age: float
    low: float
    estimate: float
    high: float
    missing: List[str]
    assumed: Dict[str, Tuple[float, float]]    # canonical interval per missing marker
    known_values: Dict[str, float]
    warnings: List[str] = field(default_factory=list)

    @property
    def width(self):
        return self.high - self.low


def _bounds(marker):
    """Values of the missing marker that give the lowest and highest PhenoAge."""
    a, b = NORMAL_RANGES[marker]
    ref = REFERENCE_PROFILE[marker]
    return (a, b) if marker_years(marker, a, ref) <= marker_years(marker, b, ref) else (b, a)


def phenoage_range_from_canonical(age, known):
    missing = [m for m in MARKERS if m not in known]
    if not missing:
        raise ValueError("No markers are missing; use phenoage_from_canonical.")
    if len(missing) > MAX_MISSING:
        raise ValueError("%d markers missing (%s); at most %d can be estimated."
                         % (len(missing), ", ".join(missing), MAX_MISSING))

    low_vals, mid_vals, high_vals = dict(known), dict(known), dict(known)
    for m in missing:
        lo, hi = _bounds(m)
        low_vals[m], high_vals[m] = lo, hi
        mid_vals[m] = REFERENCE_PROFILE[m]

    mid = phenoage_from_canonical(age, mid_vals)
    low = phenoage_from_canonical(age, low_vals).phenoage
    high = phenoage_from_canonical(age, high_vals).phenoage

    warnings = list(mid.warnings)
    warnings.append("Missing %s: assumed within the normal lab range, so this is "
                    "a range, not one number." % ", ".join(missing))
    if high - low > 5:
        warnings.append("The range is wider than 5 years; testing the missing "
                        "marker(s) would narrow it a lot.")
    return PhenoAgeRange(age, low, mid.phenoage, high, missing,
                         {m: NORMAL_RANGES[m] for m in missing}, dict(known),
                         warnings)


def phenoage_range(age, report):
    """Like core.phenoage, but `report` may leave out up to 3 markers."""
    if age <= 0:
        raise ValueError("Age must be positive.")
    known = {m: to_canonical(m, *report[m]) for m in MARKERS if m in report}
    return phenoage_range_from_canonical(age, known)


# Units as printed on Indian lab reports, for showing the assumed intervals.
REPORT_UNITS = {
    "albumin": "g/dL",
    "creatinine": "mg/dL",
    "glucose": "mg/dL",
    "crp": "mg/L",
    "lymphocyte_pct": "%",
    "mcv": "fL",
    "rdw": "%",
    "alp": "U/L",
    "wbc": "cells/cumm",
}


def describe_interval(marker):
    unit = REPORT_UNITS[marker]
    lo, hi = (round(v / factor(marker, unit), 1) for v in NORMAL_RANGES[marker])
    return "%g-%g %s" % (lo, hi, unit)
