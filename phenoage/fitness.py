"""Fitness Age from band data: a literature-based score, not a validated clock.

Each band metric is turned into a mortality hazard ratio (HR) using a
published meta-analysis, and each HR into years with the same Gompertz rate
PhenoAge uses (mortality rises about 9.4% per year of age):

    years = ln(HR) / 0.090165

So "+1 year" means "about the extra death risk of being one year older".

Sources (all-cause mortality):
- Resting HR: RR 1.09 per +10 bpm. Zhang D et al., CMAJ 2016;188(3):E53-63.
- Daily steps: HR 1.00 / 0.60 / 0.55 / 0.47 at quartile medians of
  3,553 / 5,801 / 7,842 / 10,901 steps. Paluch AE et al., Lancet Public
  Health 2022;7(3):e219-28. Benefit plateaus near 6,000-8,000 steps at 60+.
- VO2max: RR 0.87 per +1 MET (3.5 mL/kg/min). Kodama S et al., JAMA
  2009;301(19):2024-35. Reference = FRIEND registry treadmill 50th
  percentile for age and sex. Kaminsky LA et al., Mayo Clin Proc 2015.
- Sleep: RR 1.12 for short and 1.30 for long sleep vs 7-8 hours.
  Cappuccio FP et al., Sleep 2010;33(5):585-92.

Caveats: these effects come from separate studies and overlap (fit people
have lower resting HR and walk more), so adding them overstates the total.
The sum is capped at +/-5 years as a guard, not a correction. Long sleep and
very low step counts are partly markers of existing illness.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional

from .core import AGE_RATE

MAX_TOTAL_YEARS = 5.0

# Resting heart rate
RHR_RR_PER_10 = 1.09
RHR_REFERENCE = 65.0
RHR_CLAMP = (45.0, 100.0)

# Daily steps: (steps, hazard ratio) at the Paluch 2022 quartile medians.
STEPS_CURVE = [(3553, 1.00), (5801, 0.60), (7842, 0.55), (10901, 0.47)]
STEPS_REFERENCE = 7000
STEPS_PLATEAU_60_PLUS = 8000

# VO2max
VO2_RR_PER_MET = 0.87
ML_PER_MET = 3.5
VO2_MAX_METS_FROM_REFERENCE = 4.0
# FRIEND 2015 treadmill 50th percentiles, mL/kg/min, by decade midpoint.
VO2_REFERENCE = {
    "male": [(25, 48.0), (35, 42.4), (45, 37.8), (55, 32.6), (65, 28.2), (75, 24.4)],
    "female": [(25, 37.6), (35, 30.2), (45, 26.7), (55, 23.4), (65, 20.0), (75, 18.3)],
}

# Sleep duration (hours): no extra risk between 7 and 8.
SLEEP_OPTIMAL = (7.0, 8.0)
SLEEP_SHORT_FULL = 6.0    # full short-sleep RR at or below this
SLEEP_LONG_FULL = 9.0     # full long-sleep RR at or above this
SLEEP_SHORT_RR = 1.12
SLEEP_LONG_RR = 1.30


def hr_to_years(hazard_ratio):
    return math.log(hazard_ratio) / AGE_RATE


def _interpolate(points, x):
    """Linear interpolation, flat beyond the first and last points."""
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def resting_hr_years(bpm):
    bpm = min(max(bpm, RHR_CLAMP[0]), RHR_CLAMP[1])
    return hr_to_years(RHR_RR_PER_10) * (bpm - RHR_REFERENCE) / 10


def _steps_log_hr(steps):
    curve = [(s, math.log(hr)) for s, hr in STEPS_CURVE]
    return _interpolate(curve, steps)


def steps_years(steps, age):
    if age >= 60:
        steps = min(steps, STEPS_PLATEAU_60_PLUS)
    return (_steps_log_hr(steps) - _steps_log_hr(STEPS_REFERENCE)) / AGE_RATE


def vo2max_reference(age, sex):
    if sex not in VO2_REFERENCE:
        raise ValueError("sex must be 'male' or 'female' for the VO2max reference")
    return _interpolate(VO2_REFERENCE[sex], age)


def vo2max_years(vo2max, age, sex):
    mets = (vo2max - vo2max_reference(age, sex)) / ML_PER_MET
    cap = VO2_MAX_METS_FROM_REFERENCE
    mets = min(max(mets, -cap), cap)
    return hr_to_years(VO2_RR_PER_MET) * mets


def sleep_years(hours):
    low, high = SLEEP_OPTIMAL
    if hours < low:
        share = min((low - hours) / (low - SLEEP_SHORT_FULL), 1.0)
        return hr_to_years(SLEEP_SHORT_RR) * share
    if hours > high:
        share = min((hours - high) / (SLEEP_LONG_FULL - high), 1.0)
        return hr_to_years(SLEEP_LONG_RR) * share
    return 0.0


@dataclass
class MetricYears:
    metric: str
    value: float
    reference: str
    years: float


@dataclass
class FitnessAgeResult:
    chronological_age: float
    fitness_age: float
    components: List[MetricYears]
    uncapped_years: float
    warnings: List[str] = field(default_factory=list)

    @property
    def difference(self):
        return self.fitness_age - self.chronological_age


def fitness_age(age, sex=None, resting_hr=None, steps=None, sleep_hours=None,
                vo2max=None):
    """Fitness Age from whichever band metrics are available."""
    components = []
    warnings = []
    if resting_hr is not None:
        components.append(MetricYears("resting_hr", resting_hr,
                                      "%g bpm" % RHR_REFERENCE,
                                      resting_hr_years(resting_hr)))
    if steps is not None:
        components.append(MetricYears("steps", steps, "%d/day" % STEPS_REFERENCE,
                                      steps_years(steps, age)))
        if steps < STEPS_CURVE[0][0]:
            warnings.append("Very low step counts partly reflect illness or "
                            "not wearing the band, not only inactivity.")
    if sleep_hours is not None:
        components.append(MetricYears("sleep_hours", sleep_hours, "7-8 h",
                                      sleep_years(sleep_hours)))
        if sleep_hours > SLEEP_OPTIMAL[1]:
            warnings.append("Long sleep is linked to risk mostly because it "
                            "often accompanies illness; it is not proven harmful.")
    if vo2max is not None:
        if sex is None:
            warnings.append("VO2max skipped: sex is needed for its reference.")
        else:
            ref = vo2max_reference(age, sex)
            components.append(MetricYears("vo2max", vo2max, "%.1f mL/kg/min" % ref,
                                          vo2max_years(vo2max, age, sex)))
    if not components:
        raise ValueError("No band metrics given.")
    if not 20 <= age <= 79:
        warnings.append("The reference data cover ages 20-79; treat the "
                        "result with caution.")

    total = sum(c.years for c in components)
    capped = min(max(total, -MAX_TOTAL_YEARS), MAX_TOTAL_YEARS)
    if capped != total:
        warnings.append("Total of %+.1f years capped at %+.0f, because the "
                        "metrics overlap." % (total, capped))
    components.sort(key=lambda c: abs(c.years), reverse=True)
    return FitnessAgeResult(age, age + capped, components, total, warnings)
