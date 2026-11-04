"""Internal age: a blood score that tracks DNA-methylation aging.

Fitted in research/dna_age.py on NHANES 1999-2002 adults aged 50-84 who had
both routine blood tests and the CDC's DNA methylation clocks. On a locked
test set it tracked DNA internal age (GrimAge2 acceleration) with r = 0.49
vs 0.38 for PhenoAge, and DNA pace of aging (DunedinPoAm) with r = 0.49 vs
0.30 (research/RESULTS.md section 10).

- internal age = calendar age + the GrimAge2 acceleration the blood predicts,
  in years: how much older or younger the body looks inside than the
  birthday says. It is an estimate that correlates with DNA age, not a DNA
  test.
- pace estimate = the DunedinPoAm value the blood predicts (biological years
  per calendar year), from a single test.
- pace from repeat tests = the slope of internal age against calendar time.

Both scores are linear in age and the markers (CRP as ln mg/dL), so each
marker's effect in years is exact and additive.
"""

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .core import MARKERS
from .explain import REFERENCE_PROFILE
from .partial import MAX_MISSING, NORMAL_RANGES
from .units import to_canonical

with open(os.path.join(os.path.dirname(__file__), "internal_age_params.json")) as _f:
    PARAMS = json.load(_f)

FEATURES = PARAMS["features"]          # ["age"] + MARKERS, in that order
VALID_AGE_RANGE = (50, 84)
MIN_TESTS_FOR_PACE = 3
MIN_YEARS_FOR_PACE = 1.0


def _x(age, values):
    return [age] + [math.log(values[m]) if m == "crp" else values[m] for m in MARKERS]


def _weights(name):
    p = PARAMS[name]
    return [b / s for b, s in zip(p["beta"], p["sd"])]


def _predict(name, x):
    p = PARAMS[name]
    return p["intercept"] + sum((xi - m) / s * b for xi, m, s, b in zip(x, p["mu"], p["sd"], p["beta"]))


@dataclass
class InternalAgeResult:
    internal_age: float
    chronological_age: float
    baseline_gap: float               # gap for a typical healthy adult of this age
    contributions: Dict[str, float]   # years per marker vs the typical healthy value
    pace: float                       # estimated biological years per calendar year
    typical_pace: float               # NHANES average pace at this age
    warnings: List[str] = field(default_factory=list)

    @property
    def gap(self):
        """Internal age minus calendar age."""
        return self.internal_age - self.chronological_age


def internal_age_from_canonical(age, values):
    missing = [m for m in MARKERS if m not in values]
    if missing:
        raise ValueError("Missing markers: %s" % ", ".join(missing))
    x = _x(age, values)
    ref = _x(age, REFERENCE_PROFILE)
    w = _weights("grimage2")
    gap = _predict("grimage2", x)
    contributions = {m: w[i + 1] * (x[i + 1] - ref[i + 1]) for i, m in enumerate(MARKERS)}
    line = PARAMS["dunedinpoam"]["target_age_line"]
    typical = line["intercept"] + line["slope"] * age
    warnings = []
    low, high = VALID_AGE_RANGE
    if not low <= age <= high:
        warnings.append("Internal age was fitted on ages 50-84; treat it as a rough guide.")
    if values["crp"] >= 1.0:
        warnings.append("CRP is 10 mg/L or higher, usually a passing infection; it inflates "
                        "internal age. Retest when well.")
    return InternalAgeResult(age + gap, age, _predict("grimage2", ref), contributions,
                             typical + _predict("dunedinpoam", x), typical, warnings)


def internal_age(age, report):
    """Internal age from a lab report: {marker: (value, unit)}, all 9 markers."""
    values = {m: to_canonical(m, *report[m]) for m in MARKERS if m in report}
    return internal_age_from_canonical(age, values)


def internal_age_range(age, known):
    """(low, high) internal age when up to 3 markers are missing, assuming each
    missing value lies in the usual lab range. Exact, because the score is linear."""
    missing = [m for m in MARKERS if m not in known]
    if not missing:
        r = internal_age_from_canonical(age, known)
        return r.internal_age, r.internal_age
    if len(missing) > MAX_MISSING:
        raise ValueError("%d markers missing; at most 3 can be estimated." % len(missing))
    lo, hi = dict(known), dict(known)
    w = _weights("grimage2")
    for m in missing:
        a, b = NORMAL_RANGES[m]
        i = FEATURES.index(m)
        fa = math.log(a) if m == "crp" else a
        fb = math.log(b) if m == "crp" else b
        if w[i] * fa <= w[i] * fb:
            lo[m], hi[m] = a, b
        else:
            lo[m], hi[m] = b, a
    return (internal_age_from_canonical(age, lo).internal_age,
            internal_age_from_canonical(age, hi).internal_age)


@dataclass
class PaceTrend:
    pace: float                       # internal-age years per calendar year
    ci: Tuple[float, float]           # 95% CI of the slope
    n_tests: int
    years: float


def pace_from_history(points: Sequence[Tuple[float, float]]) -> Optional[PaceTrend]:
    """Slope of internal age against calendar time.

    points: (calendar time in years, internal age) for each blood test. Returns
    None until there are at least 3 tests spanning at least a year, because a
    slope from fewer points is mostly lab noise.
    """
    if len(points) < MIN_TESTS_FOR_PACE:
        return None
    ts = [p[0] for p in points]
    span = max(ts) - min(ts)
    if span < MIN_YEARS_FOR_PACE:
        return None
    n = len(points)
    tm = sum(ts) / n
    ym = sum(p[1] for p in points) / n
    sxx = sum((t - tm) ** 2 for t in ts)
    slope = sum((t - tm) * (y - ym) for t, y in points) / sxx
    resid = [y - (ym + slope * (t - tm)) for t, y in points]
    if n > 2:
        se = math.sqrt(sum(r * r for r in resid) / (n - 2) / sxx)
        # t quantiles for 95% CI by degrees of freedom; 1.96 beyond the table
        tq = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31}.get(n - 2, 1.96)
        ci = (slope - tq * se, slope + tq * se)
    else:
        ci = (float("-inf"), float("inf"))
    return PaceTrend(slope, ci, n, span)
