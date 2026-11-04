"""Break a PhenoAge result into how many years each marker adds or removes.

PhenoAge looks non-linear, but the log-log step undoes the Gompertz
exponential exactly:

    PhenoAge = 141.50 + ln(0.00553 * H) / 0.0902,   H = exp(xb) * K
             = constant + xb / 0.0902

So PhenoAge is a straight line in the weighted sum xb, and each marker's
effect in years is simply coefficient * (value - reference) / 0.0902. The
contributions add up exactly; there is no interaction between markers.

Contributions are measured against a reference profile: a person of the same
age whose markers sit at the reference values. Change the reference and the
split between "baseline" and "markers" changes, but the total does not.
"""

import math
from dataclasses import dataclass
from typing import List

from .core import (AGE_COEFFICIENT, AGE_RATE, COEFFICIENTS, MARKERS,
                   PhenoAgeResult, phenoage_from_canonical)

# Typical healthy adult values (mid reference ranges on Indian lab reports),
# in canonical units. These are a chosen yardstick, not population medians.
REFERENCE_PROFILE = {
    "albumin": 44.0,        # 4.4 g/dL
    "creatinine": 79.6,     # 0.9 mg/dL
    "glucose": 5.0,         # 90 mg/dL
    "crp": 0.1,             # 1.0 mg/L
    "lymphocyte_pct": 30.0,
    "mcv": 90.0,
    "rdw": 13.0,
    "alp": 70.0,
    "wbc": 6.5,             # 6,500 cells/cumm
}


@dataclass
class MarkerContribution:
    marker: str
    value: float        # canonical units
    reference: float    # canonical units
    years: float        # positive = makes you biologically older


@dataclass
class Explanation:
    phenoage: float
    chronological_age: float
    baseline_phenoage: float     # PhenoAge with every marker at reference
    contributions: List[MarkerContribution]   # largest effect first

    @property
    def baseline_gap(self):
        """How far the reference profile itself sits from calendar age."""
        return self.baseline_phenoage - self.chronological_age


def _term(marker, value):
    x = math.log(value) if marker == "crp" else value
    return COEFFICIENTS[marker] * x


def marker_years(marker, value, reference):
    """Years added (positive) or removed by one marker vs its reference."""
    return (_term(marker, value) - _term(marker, reference)) / AGE_RATE


def years_per_unit(marker):
    """Years per one canonical unit increase (CRP: per doubling)."""
    if marker == "crp":
        return COEFFICIENTS[marker] * math.log(2) / AGE_RATE
    return COEFFICIENTS[marker] / AGE_RATE


def years_per_year_of_age():
    """Each calendar year adds about 0.89 years of PhenoAge on its own."""
    return AGE_COEFFICIENT / AGE_RATE


def explain(result: PhenoAgeResult, reference=None):
    """Split a PhenoAge result into a baseline and per-marker years."""
    reference = dict(REFERENCE_PROFILE if reference is None else reference)
    missing = [m for m in MARKERS if m not in reference]
    if missing:
        raise ValueError("Reference profile is missing: %s" % ", ".join(missing))

    baseline = phenoage_from_canonical(result.chronological_age, reference).phenoage
    contributions = [
        MarkerContribution(m, result.canonical_values[m], reference[m],
                           marker_years(m, result.canonical_values[m], reference[m]))
        for m in MARKERS
    ]
    contributions.sort(key=lambda c: abs(c.years), reverse=True)
    return Explanation(result.phenoage, result.chronological_age, baseline,
                       contributions)
