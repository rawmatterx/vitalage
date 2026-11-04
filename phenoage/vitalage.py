"""VitalAge v1 (beta): one number from internal age and band data.

    VitalAge = internal age + band adjustment
    band adjustment = clamp(BAND_WEIGHT x (Fitness Age - calendar age), -BAND_CAP, +BAND_CAP)

- Internal age (internal.py) is the validated part: a blood score that tracks
  DNA-methylation aging (NHANES 1999-2002).
- The band adjustment comes from Fitness Age (fitness.py), which is built
  from published mortality meta-analyses, not fitted to DNA aging. Its weight
  (0.5) and cap (+/-3 years) are a judgment call, chosen so the validated
  blood part always dominates.

The weights are fixed for this version. They will be refitted on pilot data
from people with a blood panel, band data and a DNA-age test
(research/PILOT_PROTOCOL.md); any change becomes a new version, so a
person's history stays comparable.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Sequence, Tuple

from .internal import pace_from_history

VERSION = "v1-beta"
BAND_WEIGHT = 0.5
BAND_CAP = 3.0
STALE_BLOOD_DAYS = 365


@dataclass
class VitalAgeResult:
    vitalage: float
    chronological_age: float
    internal_age: float
    band_adjustment: Optional[float]      # None when no band data
    blood_date: Optional[date] = None
    as_of: Optional[date] = None
    version: str = VERSION
    warnings: List[str] = field(default_factory=list)

    @property
    def gap(self):
        return self.vitalage - self.chronological_age

    @property
    def blood_years(self):
        """Internal age minus calendar age."""
        return self.internal_age - self.chronological_age


def band_adjustment(age, fitness_age):
    raw = BAND_WEIGHT * (fitness_age - age)
    return max(-BAND_CAP, min(BAND_CAP, raw))


def vitalage(age, internal_age, fitness_age=None, blood_date=None, as_of=None):
    """Combine internal age (from blood) with Fitness Age (from the band).

    age is calendar age on `as_of`. internal_age may come from an earlier
    blood test (blood_date); it is then shifted forward by the time elapsed,
    because the body is assumed to have aged at calendar speed since then.
    """
    warnings = []
    if blood_date is not None and as_of is not None:
        elapsed = (as_of - blood_date).days
        if elapsed < 0:
            raise ValueError("The blood test is dated after the VitalAge date.")
        internal_age = internal_age + elapsed / 365.2425
        if elapsed > STALE_BLOOD_DAYS:
            warnings.append("Your last blood test is %d months old; VitalAge mostly reflects your "
                            "band until you retest." % round(elapsed / 30.44))
    adj = None if fitness_age is None else band_adjustment(age, fitness_age)
    if adj is None:
        warnings.append("No band data, so VitalAge equals internal age.")
    elif abs(BAND_WEIGHT * (fitness_age - age)) > BAND_CAP:
        warnings.append("The band adjustment was capped at %+.0f years." % adj)
    value = internal_age + (adj or 0.0)
    return VitalAgeResult(value, age, internal_age, adj, blood_date, as_of, VERSION, warnings)


def vitalage_pace(points: Sequence[Tuple[float, float]]):
    """Pace of VitalAge: slope across time points (years, VitalAge), with a 95% CI.
    Same rules as internal-age pace: 3+ points spanning at least a year."""
    return pace_from_history(points)
