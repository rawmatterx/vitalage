"""VitalAge: one combined age from PhenoAge and daily steps.

Fitted by research/fit_model.py on NHANES 2005-2006 (2,885 adults, 535
deaths, NCHS linked mortality through 2019) and kept only because it beat
PhenoAge alone on held-out data (5-fold cross-validated C-index +0.006,
95% CI +0.002 to +0.010). Full methods and limits: research/RESULTS.md.

Model: Gompertz proportional hazards on months since the exam with
    eta = b0 + b_age * age + b_accel * accel + b_steps * ln(hip_steps)
where accel is PhenoAge minus its trend on age in NHANES, limited to the
1st-99th percentile range (-12.5 to +29.4 years). As with PhenoAge
(Levine et al. 2018), eta is turned into an age: the age whose 10-year
mortality in an age-only Gompertz model on the same people equals this
person's 10-year mortality. That mapping is linear in eta,

    VitalAge = (eta + K - a0) / a_age,

so VitalAge splits exactly into a baseline plus years from blood and steps.

Steps: the model uses hip ActiGraph 7164 steps counted in minutes with
>= 500 counts. Wrist bands count about 1,400 more steps a day than hip
ActiGraphs, so band steps are converted as band - 1,400. That conversion is
uncertain (limits of agreement roughly -2,300 to +5,200 steps/day), and the
result reports the VitalAge range it implies.
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple

# From research/combined_params.json (tests check they match).
AGE_MODEL = {"b0": -13.200025874398705, "b_age": 0.09464351804515815,
             "gamma": 0.009287803205646459}
COMBINED_MODEL = {"b0": -8.38502130499207, "b_age": 0.08253806274719121,
                  "b_pheno_accel": 0.040231009990789504,
                  "b_log_steps": -0.5237108253875615, "gamma": 0.011370643974707117}
K = 0.1501436511192038
ACCEL_INTERCEPT = -7.155944354779851
ACCEL_SLOPE = 1.0604280372675574
ACCEL_CLIP = (-12.450650043285348, 29.37951112708095)
REFERENCE_HIP_STEPS = 5784.571428571428

BAND_TO_HIP_OFFSET = 1400.0
# 95% limits of agreement for (band - hip) steps/day, wrist Fitbit vs hip GT3X
BAND_MINUS_HIP_LOA = (-2300.0, 5200.0)
MIN_HIP_STEPS = 500.0
VALID_AGE_RANGE = (20, 84)


@dataclass
class VitalAgeResult:
    vitalage: float
    chronological_age: float
    baseline: float               # same age, typical blood (no acceleration), median steps
    blood_years: float            # from PhenoAge acceleration
    steps_years: float            # from steps vs the NHANES median
    hip_steps: float              # band steps converted to the model's scale
    steps_range: Tuple[float, float]   # VitalAge across the band-to-hip uncertainty
    warnings: List[str] = field(default_factory=list)

    @property
    def difference(self):
        return self.vitalage - self.chronological_age


def band_to_hip_steps(band_steps, band_minus_hip=BAND_TO_HIP_OFFSET):
    return max(band_steps - band_minus_hip, MIN_HIP_STEPS)


def pheno_acceleration(age, phenoage):
    """PhenoAge minus its average for this age in NHANES 2003-2006, limited to
    the 1st-99th percentile range the model was fitted on."""
    raw = phenoage - (ACCEL_INTERCEPT + ACCEL_SLOPE * age)
    return min(max(raw, ACCEL_CLIP[0]), ACCEL_CLIP[1])


def _to_age(eta):
    return (eta + K - AGE_MODEL["b0"]) / AGE_MODEL["b_age"]


def _eta(age, accel, hip_steps):
    c = COMBINED_MODEL
    return (c["b0"] + c["b_age"] * age + c["b_pheno_accel"] * accel
            + c["b_log_steps"] * math.log(hip_steps))


def vitalage(age, phenoage, band_steps):
    """Combined VitalAge from age, PhenoAge and typical daily band steps."""
    if band_steps <= 0:
        raise ValueError("Steps per day must be positive.")
    accel = pheno_acceleration(age, phenoage)
    hip = band_to_hip_steps(band_steps)
    value = _to_age(_eta(age, accel, hip))
    baseline = _to_age(_eta(age, 0.0, REFERENCE_HIP_STEPS))
    per_year = 1.0 / AGE_MODEL["b_age"]
    blood = COMBINED_MODEL["b_pheno_accel"] * accel * per_year
    steps = COMBINED_MODEL["b_log_steps"] * (math.log(hip) - math.log(REFERENCE_HIP_STEPS)) * per_year

    ends = [_to_age(_eta(age, accel, band_to_hip_steps(band_steps, d))) for d in BAND_MINUS_HIP_LOA]
    warnings = []
    low, high = VALID_AGE_RANGE
    if not low <= age <= high:
        warnings.append("VitalAge was fitted on ages 20-84; treat the result with caution.")
    if hip == MIN_HIP_STEPS:
        warnings.append("Very low step counts partly reflect illness or not wearing the band.")
    return VitalAgeResult(value, age, baseline, blood, steps, hip,
                          (min(ends), max(ends)), warnings)
