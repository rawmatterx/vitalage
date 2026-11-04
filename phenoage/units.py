"""Convert lab report values into the units the PhenoAge formula expects.

Indian lab reports mostly use "conventional" units (g/dL, mg/dL, mg/L,
cells/cumm). Levine's PhenoAge formula was fitted on SI-style units
(g/L, umol/L, mmol/L) and on CRP in mg/dL. Getting this wrong is the most
common way to get a nonsense PhenoAge, so every value goes through here.
"""

# Canonical unit for each marker, i.e. the unit the formula uses.
CANONICAL_UNITS = {
    "albumin": "g/L",
    "creatinine": "umol/L",
    "glucose": "mmol/L",
    "crp": "mg/dL",
    "lymphocyte_pct": "%",
    "mcv": "fL",
    "rdw": "%",
    "alp": "U/L",
    "wbc": "10^3/uL",
}

# Multiply a value in the given unit by this factor to get the canonical unit.
# Keys are normalised unit strings (see _normalise_unit).
_FACTORS = {
    "albumin": {"g/l": 1.0, "g/dl": 10.0},
    "creatinine": {"umol/l": 1.0, "mg/dl": 88.42},
    "glucose": {"mmol/l": 1.0, "mg/dl": 1 / 18.016},
    "crp": {"mg/dl": 1.0, "mg/l": 0.1},
    "lymphocyte_pct": {"%": 1.0},
    "mcv": {"fl": 1.0},
    "rdw": {"%": 1.0},
    "alp": {"u/l": 1.0, "iu/l": 1.0},
    "wbc": {
        "10^3/ul": 1.0,
        "10^9/l": 1.0,
        "thou/ul": 1.0,
        "cells/ul": 0.001,
        "cells/cumm": 0.001,
        "/cumm": 0.001,
        "/ul": 0.001,
    },
}

# Plausible ranges in canonical units. A value outside these almost always
# means the wrong unit was picked (e.g. albumin 4.2 entered as g/L).
PLAUSIBLE_RANGES = {
    "albumin": (15.0, 60.0),
    "creatinine": (20.0, 1500.0),
    "glucose": (2.0, 35.0),
    "crp": (0.001, 30.0),
    "lymphocyte_pct": (1.0, 80.0),
    "mcv": (50.0, 130.0),
    "rdw": (9.0, 30.0),
    "alp": (10.0, 1000.0),
    "wbc": (0.5, 50.0),
}


def _normalise_unit(unit):
    u = unit.strip().lower().replace(" ", "")
    u = u.replace("µ", "u").replace("μ", "u")  # micro sign and Greek mu
    u = u.replace("mm3", "cumm").replace("cu.mm", "cumm")
    u = u.replace("x10^3", "10^3").replace("x10^9", "10^9")
    return u


def accepted_units(marker):
    """List the unit spellings accepted for a marker."""
    return sorted(_FACTORS[marker])


def to_canonical(marker, value, unit):
    """Convert one lab value to the formula's unit and sanity-check it.

    Raises ValueError for an unknown marker or unit, a non-positive value,
    or a converted value outside the plausible range.
    """
    if marker not in _FACTORS:
        raise ValueError("Unknown marker '%s'. Expected one of: %s"
                         % (marker, ", ".join(sorted(_FACTORS))))
    factors = _FACTORS[marker]
    key = _normalise_unit(unit)
    if key not in factors:
        raise ValueError("Unit '%s' not supported for %s. Use one of: %s"
                         % (unit, marker, ", ".join(accepted_units(marker))))
    if value <= 0:
        raise ValueError("%s must be greater than 0 (got %s). For CRP reported "
                         "as below the detection limit, enter the limit itself, "
                         "e.g. '<0.5 mg/L' -> 0.5 mg/L." % (marker, value))

    converted = value * factors[key]
    low, high = PLAUSIBLE_RANGES[marker]
    if not low <= converted <= high:
        raise ValueError(
            "%s = %s %s converts to %.4g %s, outside the plausible range "
            "%s-%s %s. Check the unit on the report."
            % (marker, value, unit, converted, CANONICAL_UNITS[marker],
               low, high, CANONICAL_UNITS[marker]))
    return converted
