"""Levine's Phenotypic Age (PhenoAge).

Source: Levine ME et al. "An epigenetic biomarker of aging for lifespan and
healthspan", Aging 2018;10(4):573-591, and Liu Z et al., PLOS Medicine 2018.
The coefficients below are the published ones, at the full precision used by
the BioAge R package (Kwon & Belsky 2021, R/phenoage_calc.R). Do not tune
them by hand.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List

from .units import to_canonical

INTERCEPT = -19.90667
AGE_COEFFICIENT = 0.08035356

# Coefficient per marker, in canonical units (see units.CANONICAL_UNITS).
# CRP enters the formula as its natural log.
COEFFICIENTS = {
    "albumin": -0.03359355,
    "creatinine": 0.009506491,
    "glucose": 0.1953192,
    "crp": 0.09536762,
    "lymphocyte_pct": -0.01199984,
    "mcv": 0.02676401,
    "rdw": 0.3306156,
    "alp": 0.001868778,
    "wbc": 0.05542406,
}

MARKERS = tuple(COEFFICIENTS)

# Gompertz mortality model constants.
GAMMA = 0.007692696      # Gompertz shape per month
HORIZON_MONTHS = 120     # 10-year mortality
AGE_RATE = 0.090165      # how fast mortality rises per year of age
AGE_OFFSET = 141.50225
SCALE = 0.0055305

# PhenoAge was fitted on NHANES adults roughly 20-84 years old.
VALID_AGE_RANGE = (20, 84)


@dataclass
class PhenoAgeResult:
    phenoage: float
    chronological_age: float
    mortality_10yr: float          # estimated 10-year mortality risk, 0-1
    linear_predictor: float
    canonical_values: Dict[str, float]
    warnings: List[str] = field(default_factory=list)

    @property
    def acceleration(self):
        """PhenoAge minus chronological age. Positive = older than your years."""
        return self.phenoage - self.chronological_age


def linear_predictor(age, values):
    """Weighted sum of age and markers (canonical units)."""
    xb = INTERCEPT + AGE_COEFFICIENT * age
    for marker in MARKERS:
        x = values[marker]
        if marker == "crp":
            x = math.log(x)
        xb += COEFFICIENTS[marker] * x
    return xb


def _cumulative_hazard(xb):
    return math.exp(xb) * (math.exp(HORIZON_MONTHS * GAMMA) - 1) / GAMMA


def phenoage_from_canonical(age, values):
    """PhenoAge from values already in canonical units."""
    missing = [m for m in MARKERS if m not in values]
    if missing:
        raise ValueError("Missing markers: %s" % ", ".join(missing))

    xb = linear_predictor(age, values)
    hazard = _cumulative_hazard(xb)
    mortality = -math.expm1(-hazard)
    # The published form is 141.50 + ln(-0.00553 * ln(1 - M)) / 0.0902.
    # Since ln(1 - M) = -hazard, we use the hazard directly: same result,
    # but no rounding trouble when M is very close to 0 or 1.
    pheno = AGE_OFFSET + math.log(SCALE * hazard) / AGE_RATE

    warnings = []
    low, high = VALID_AGE_RANGE
    if not low <= age <= high:
        warnings.append("Age %s is outside the %d-%d range PhenoAge was "
                        "fitted on; treat the result with caution."
                        % (age, low, high))
    if values["crp"] >= 1.0:
        warnings.append("CRP is 10 mg/L or higher, which usually means an "
                        "acute infection or inflammation. Retest when well.")

    return PhenoAgeResult(
        phenoage=pheno,
        chronological_age=age,
        mortality_10yr=mortality,
        linear_predictor=xb,
        canonical_values=dict(values),
        warnings=warnings,
    )


def phenoage(age, report):
    """PhenoAge from a lab report.

    report maps each marker name to a (value, unit) pair, for example
    {"albumin": (4.3, "g/dL"), "crp": (1.2, "mg/L"), ...}.
    """
    if age <= 0:
        raise ValueError("Age must be positive.")
    missing = [m for m in MARKERS if m not in report]
    if missing:
        raise ValueError("Missing markers: %s" % ", ".join(missing))
    canonical = {m: to_canonical(m, *report[m]) for m in MARKERS}
    return phenoage_from_canonical(age, canonical)
